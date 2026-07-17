from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.monitors.constants import Severity


class AlertRule(models.Model):
    """User-configured condition → actions mapping, evaluated per event."""

    class TriggerOn(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed events"
        REVERTED = "reverted", "Reverted events (reorg)"

    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="alert_rules"
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    # ---- filters (all optional; unset = match everything) -------------------
    wallet_monitor = models.ForeignKey(
        "monitors.WalletMonitor", null=True, blank=True, on_delete=models.CASCADE, related_name="alert_rules"
    )
    contract_monitor = models.ForeignKey(
        "monitors.ContractMonitor", null=True, blank=True, on_delete=models.CASCADE, related_name="alert_rules"
    )
    chain = models.ForeignKey(
        "chains.Chain", null=True, blank=True, on_delete=models.CASCADE, related_name="alert_rules"
    )
    event_types = models.JSONField(default=list, blank=True)
    token_address = models.CharField(max_length=42, blank=True, default="")
    min_amount_wei = models.DecimalField(max_digits=78, decimal_places=0, null=True, blank=True)
    max_amount_wei = models.DecimalField(max_digits=78, decimal_places=0, null=True, blank=True)
    from_address = models.CharField(max_length=42, blank=True, default="")
    to_address = models.CharField(max_length=42, blank=True, default="")
    spender_address = models.CharField(max_length=42, blank=True, default="")
    topic0 = models.CharField(max_length=66, blank=True, default="")
    trigger_on = models.CharField(
        max_length=10, choices=TriggerOn.choices, default=TriggerOn.CONFIRMED
    )

    # ---- alert shaping -------------------------------------------------------
    severity = models.CharField(
        max_length=10, choices=Severity.choices, blank=True, default="",
        help_text="Blank inherits the event's severity.",
    )
    cooldown_seconds = models.PositiveIntegerField(
        default=0, help_text="Suppress repeat alerts for the same fingerprint for N seconds."
    )
    group_window_seconds = models.PositiveIntegerField(
        default=0,
        help_text="Fold repeat alerts within N seconds into one grouped alert (debounce).",
    )

    # ---- actions ---------------------------------------------------------------
    notify_in_app = models.BooleanField(default=True)
    notify_email = models.BooleanField(default=False)
    webhook = models.ForeignKey(
        "webhooks.WebhookEndpoint", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="alert_rules",
        help_text="Deliver to this endpoint. Blank = all endpoints subscribed to alert.triggered.",
    )
    notify_webhook = models.BooleanField(default=False)
    telegram_enabled = models.BooleanField(default=False)  # placeholder integration
    slack_enabled = models.BooleanField(default=False)  # placeholder integration

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "cs_alert_rule"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["workspace", "is_active"])]

    def __str__(self) -> str:
        return self.name


class Alert(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        RESOLVED = "resolved", "Resolved"

    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="alerts"
    )
    rule = models.ForeignKey(
        AlertRule, null=True, blank=True, on_delete=models.SET_NULL, related_name="alerts"
    )
    event = models.ForeignKey(
        "events.BlockchainEvent", null=True, blank=True, on_delete=models.SET_NULL, related_name="alerts"
    )
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MEDIUM)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN, db_index=True)

    dedupe_key = models.CharField(max_length=200, unique=True)
    group_key = models.CharField(max_length=200, blank=True, default="", db_index=True)
    count = models.PositiveIntegerField(default=1)  # grouped occurrences
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)

    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "cs_alert"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workspace", "status"]),
            models.Index(fields=["workspace", "severity"]),
            models.Index(fields=["workspace", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"[{self.severity}] {self.title}"


class AlertNote(models.Model):
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cs_alert_note"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Note on alert {self.alert_id}"
