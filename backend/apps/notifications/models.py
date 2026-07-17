from django.conf import settings
from django.db import models

from apps.monitors.constants import Severity


class Notification(models.Model):
    class Type(models.TextChoices):
        ALERT = "alert", "Alert"
        WEBHOOK_FAILED = "webhook_failed", "Webhook failed"
        PROVIDER_OUTAGE = "provider_outage", "Provider outage"
        WORKSPACE = "workspace", "Workspace"
        SYSTEM = "system", "System"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    workspace = models.ForeignKey(
        "workspaces.Workspace", null=True, blank=True, on_delete=models.CASCADE, related_name="notifications"
    )
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.SYSTEM)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.INFO)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=300, blank=True, default="")
    alert = models.ForeignKey(
        "alerts.Alert", null=True, blank=True, on_delete=models.SET_NULL, related_name="notifications"
    )
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "cs_notification"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read_at"])]

    def __str__(self) -> str:
        return f"{self.user_id}: {self.title[:50]}"


class NotificationPreference(models.Model):
    """Per-user delivery preferences (global across workspaces)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_prefs"
    )
    min_severity_in_app = models.CharField(
        max_length=10, choices=Severity.choices, default=Severity.INFO
    )
    min_severity_email = models.CharField(
        max_length=10, choices=Severity.choices, default=Severity.HIGH
    )
    email_critical_alerts = models.BooleanField(default=True)
    email_failed_webhooks = models.BooleanField(default=True)
    email_provider_outage = models.BooleanField(default=True)
    email_daily_summary = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cs_notification_preference"

    def __str__(self) -> str:
        return f"Prefs<{self.user.email}>"

    @classmethod
    def for_user(cls, user) -> "NotificationPreference":
        prefs, _ = cls.objects.get_or_create(user=user)
        return prefs
