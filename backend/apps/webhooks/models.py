import secrets

from django.conf import settings
from django.db import models

from .crypto import decrypt_secret, encrypt_secret

WEBHOOK_EVENT_TYPES: list[tuple[str, str]] = [
    ("alert.triggered", "Alert triggered"),
    ("alert.resolved", "Alert resolved"),
    ("event.confirmed", "Blockchain event confirmed"),
    ("monitor.paused", "Monitor paused"),
    ("provider.unhealthy", "RPC provider unhealthy"),
    ("test.ping", "Test ping"),
]
WEBHOOK_EVENT_TYPE_VALUES = {value for value, _ in WEBHOOK_EVENT_TYPES}


class WebhookEndpoint(models.Model):
    """An outbound destination. The signing secret is encrypted at rest and
    only ever returned once — at creation or regeneration."""

    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="webhooks"
    )
    name = models.CharField(max_length=120)
    url = models.URLField(max_length=500)
    secret_encrypted = models.TextField()
    enabled = models.BooleanField(default=True)
    event_types = models.JSONField(default=list)  # subset of WEBHOOK_EVENT_TYPES
    max_retries = models.PositiveIntegerField(default=5)
    timeout_seconds = models.PositiveIntegerField(default=10)

    last_status = models.CharField(max_length=20, blank=True, default="")
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_failure_reason = models.CharField(max_length=500, blank=True, default="")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cs_webhook_endpoint"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["workspace", "enabled"])]

    def __str__(self) -> str:
        return f"{self.name} → {self.url[:60]}"

    # -- secret handling ------------------------------------------------------
    @staticmethod
    def generate_secret() -> str:
        return f"whsec_{secrets.token_urlsafe(32)}"

    def set_secret(self, raw: str) -> None:
        self.secret_encrypted = encrypt_secret(raw)

    def get_secret(self) -> str:
        return decrypt_secret(self.secret_encrypted)

    def subscribes_to(self, event_type: str) -> bool:
        return event_type in (self.event_types or [])


class WebhookDelivery(models.Model):
    """One logical delivery (with up to `max_attempts` attempts)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        RETRYING = "retrying", "Retrying"
        EXHAUSTED = "exhausted", "Exhausted (gave up)"

    endpoint = models.ForeignKey(WebhookEndpoint, on_delete=models.CASCADE, related_name="deliveries")
    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="webhook_deliveries"
    )
    event_type = models.CharField(max_length=50, db_index=True)
    payload = models.JSONField()
    idempotency_key = models.CharField(max_length=250, unique=True)

    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    attempt_count = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)
    response_status = models.IntegerField(null=True, blank=True)
    response_time_ms = models.IntegerField(null=True, blank=True)
    failure_reason = models.CharField(max_length=500, blank=True, default="")
    next_retry_at = models.DateTimeField(null=True, blank=True, db_index=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    replay_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="replays"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "cs_webhook_delivery"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workspace", "status"]),
            models.Index(fields=["endpoint", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} → {self.endpoint.name} [{self.status}]"
