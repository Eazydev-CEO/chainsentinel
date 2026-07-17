from django.conf import settings
from django.db import models

from apps.monitors.constants import EventType, Severity


class BlockCheckpoint(models.Model):
    """Per-chain progress marker + recent-hash ring buffer for reorg detection."""

    chain = models.OneToOneField("chains.Chain", on_delete=models.CASCADE, related_name="checkpoint")
    last_processed_block = models.BigIntegerField(default=0)
    last_processed_hash = models.CharField(max_length=66, blank=True)
    recent_blocks = models.JSONField(default=list, blank=True)  # [{"number": n, "hash": "0x…"}]
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cs_block_checkpoint"

    def __str__(self) -> str:
        return f"{self.chain.slug} @ {self.last_processed_block}"

    def advance(self, block_number: int, block_hash: str) -> None:
        window = getattr(settings, "ENGINE_REORG_WINDOW", 64)
        ring = [b for b in (self.recent_blocks or []) if b["number"] < block_number]
        ring.append({"number": block_number, "hash": block_hash.lower()})
        self.recent_blocks = ring[-window:]
        self.last_processed_block = block_number
        self.last_processed_hash = block_hash.lower()
        self.save(update_fields=["last_processed_block", "last_processed_hash", "recent_blocks", "updated_at"])

    def rewind_to(self, block_number: int) -> None:
        ring = [b for b in (self.recent_blocks or []) if b["number"] <= block_number]
        self.recent_blocks = ring
        self.last_processed_block = block_number
        self.last_processed_hash = ring[-1]["hash"] if ring else ""
        self.save(update_fields=["last_processed_block", "last_processed_hash", "recent_blocks", "updated_at"])


class EventStatus(models.TextChoices):
    PENDING = "pending", "Pending confirmations"
    CONFIRMED = "confirmed", "Confirmed"
    REVERTED = "reverted", "Reverted (reorg)"
    FAILED = "failed", "Failed"
    IGNORED = "ignored", "Ignored"


class BlockchainEvent(models.Model):
    """A detected on-chain occurrence relevant to one monitor.

    `idempotency_key` makes detection safe across retries, worker restarts
    and reorg reprocessing: the same on-chain fact never creates two rows.
    """

    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="events"
    )
    chain = models.ForeignKey("chains.Chain", on_delete=models.PROTECT, related_name="events")
    wallet_monitor = models.ForeignKey(
        "monitors.WalletMonitor", null=True, blank=True, on_delete=models.CASCADE, related_name="events"
    )
    contract_monitor = models.ForeignKey(
        "monitors.ContractMonitor", null=True, blank=True, on_delete=models.CASCADE, related_name="events"
    )

    event_type = models.CharField(max_length=30, choices=EventType.choices, db_index=True)
    status = models.CharField(
        max_length=10, choices=EventStatus.choices, default=EventStatus.PENDING
    )
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MEDIUM)
    is_large = models.BooleanField(default=False)

    block_number = models.BigIntegerField()
    block_hash = models.CharField(max_length=66)
    tx_hash = models.CharField(max_length=66)
    tx_index = models.IntegerField(null=True, blank=True)
    log_index = models.IntegerField(null=True, blank=True)  # null for native transfers

    from_address = models.CharField(max_length=42, blank=True, default="")
    to_address = models.CharField(max_length=42, blank=True, default="")
    spender_address = models.CharField(max_length=42, blank=True, default="")
    contract_address = models.CharField(max_length=42, blank=True, default="")
    token_address = models.CharField(max_length=42, blank=True, default="")
    token_symbol = models.CharField(max_length=32, blank=True, default="")
    token_decimals = models.IntegerField(null=True, blank=True)
    token_id = models.CharField(max_length=100, blank=True, default="")  # NFT token id

    amount_wei = models.DecimalField(max_digits=78, decimal_places=0, null=True, blank=True)

    event_signature = models.CharField(max_length=300, blank=True, default="")
    topic0 = models.CharField(max_length=66, blank=True, default="")
    decoded = models.JSONField(null=True, blank=True)
    raw = models.JSONField(null=True, blank=True)
    decode_error = models.CharField(max_length=300, blank=True, default="")

    confirmations_required = models.PositiveIntegerField(default=12)
    occurred_at = models.DateTimeField(null=True, blank=True)  # block timestamp
    confirmed_at = models.DateTimeField(null=True, blank=True)
    reverted_at = models.DateTimeField(null=True, blank=True)

    idempotency_key = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "cs_blockchain_event"
        ordering = ["-block_number", "-log_index"]
        indexes = [
            models.Index(fields=["chain", "block_number"]),
            models.Index(fields=["tx_hash"]),
            models.Index(fields=["from_address"]),
            models.Index(fields=["to_address"]),
            models.Index(fields=["token_address"]),
            models.Index(fields=["topic0"]),
            models.Index(fields=["workspace", "created_at"]),
            models.Index(fields=["status", "chain"]),
            models.Index(fields=["workspace", "event_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} {self.tx_hash[:10]}… ({self.status})"

    @property
    def monitor(self):
        return self.wallet_monitor or self.contract_monitor


class ReorgIncident(models.Model):
    """A detected chain reorganization, kept for admin review."""

    chain = models.ForeignKey("chains.Chain", on_delete=models.CASCADE, related_name="reorg_incidents")
    fork_block = models.BigIntegerField()
    depth = models.PositiveIntegerField()
    events_reverted = models.PositiveIntegerField(default=0)
    details = models.JSONField(default=dict, blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cs_reorg_incident"
        ordering = ["-detected_at"]

    def __str__(self) -> str:
        return f"Reorg on {self.chain.slug} at #{self.fork_block} (depth {self.depth})"
