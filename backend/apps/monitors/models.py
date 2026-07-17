from django.conf import settings
from django.db import models

from .constants import Direction, MonitorEventCategory, Severity


class ContractAbi(models.Model):
    """A validated, deduplicated ABI document owned by a workspace."""

    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="abis"
    )
    name = models.CharField(max_length=120)
    abi = models.JSONField()
    sha256 = models.CharField(max_length=64, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cs_contract_abi"
        constraints = [
            models.UniqueConstraint(fields=["workspace", "sha256"], name="uniq_workspace_abi")
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.sha256[:8]})"


class MonitorBase(models.Model):
    """Shared fields for wallet & contract monitors."""

    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="%(class)ss"
    )
    chain = models.ForeignKey("chains.Chain", on_delete=models.PROTECT, related_name="%(class)ss")
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=42, db_index=True)  # EIP-55 checksummed
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MEDIUM)
    is_active = models.BooleanField(default=True)
    tags = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    confirmations_override = models.PositiveIntegerField(
        null=True, blank=True, help_text="Overrides the chain's default confirmation count."
    )
    last_processed_block = models.BigIntegerField(default=0)
    last_event_at = models.DateTimeField(null=True, blank=True)
    error_count = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def required_confirmations(self) -> int:
        if self.confirmations_override is not None:
            return self.confirmations_override
        return self.chain.required_confirmations


class WalletMonitor(MonitorBase):
    direction = models.CharField(max_length=10, choices=Direction.choices, default=Direction.BOTH)
    event_types = models.JSONField(
        default=list,
        help_text="Categories: native_transfer, erc20_transfer, nft_transfer, approval",
    )
    token_contract = models.CharField(
        max_length=42, blank=True, default="", help_text="Optional ERC-20/721 contract filter."
    )
    min_value_wei = models.DecimalField(
        max_digits=78, decimal_places=0, null=True, blank=True,
        help_text="Ignore transfers below this raw value (wei / token base units).",
    )
    large_tx_threshold_wei = models.DecimalField(
        max_digits=78, decimal_places=0, null=True, blank=True,
        help_text="Flag transfers at/above this raw value as large.",
    )

    class Meta:
        db_table = "cs_wallet_monitor"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "chain", "address"], name="uniq_wallet_monitor"
            )
        ]
        indexes = [
            models.Index(fields=["chain", "is_active"]),
            models.Index(fields=["workspace", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} [{self.address[:10]}… on {self.chain.slug}]"

    def watches(self, category: str) -> bool:
        return category in (self.event_types or [])


class ContractMonitor(MonitorBase):
    label = models.CharField(max_length=120, blank=True)
    abi_document = models.ForeignKey(
        ContractAbi, null=True, blank=True, on_delete=models.SET_NULL, related_name="monitors"
    )
    selected_events = models.JSONField(
        default=list, help_text="Event names from the ABI to monitor."
    )
    topic_filters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Per-event indexed-parameter filters: {event: {param: value}}.",
    )

    class Meta:
        db_table = "cs_contract_monitor"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "chain", "address"], name="uniq_contract_monitor"
            )
        ]
        indexes = [
            models.Index(fields=["chain", "is_active"]),
            models.Index(fields=["workspace", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} [{self.address[:10]}… on {self.chain.slug}]"


class EventSubscription(models.Model):
    """A concrete (contract, event) subscription derived from the monitor's ABI."""

    contract_monitor = models.ForeignKey(
        ContractMonitor, on_delete=models.CASCADE, related_name="subscriptions"
    )
    event_name = models.CharField(max_length=120)
    signature = models.CharField(max_length=300)
    topic0 = models.CharField(max_length=66, db_index=True)
    abi_fragment = models.JSONField()
    indexed_filters = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cs_event_subscription"
        constraints = [
            models.UniqueConstraint(
                fields=["contract_monitor", "signature"], name="uniq_monitor_event_signature"
            )
        ]

    def __str__(self) -> str:
        return f"{self.contract_monitor.name}:{self.event_name}"


class MonitorCsvImport(models.Model):
    """Row-level report of a wallet-monitor CSV import."""

    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="csv_imports"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    filename = models.CharField(max_length=255)
    total_rows = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    report = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cs_monitor_csv_import"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"CSV import {self.filename} ({self.created_count}/{self.total_rows})"
