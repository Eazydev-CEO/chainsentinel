from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Immutable record of security-relevant actions."""

    workspace = models.ForeignKey(
        "workspaces.Workspace", null=True, blank=True, on_delete=models.CASCADE, related_name="audit_logs"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_logs"
    )
    actor_label = models.CharField(max_length=200, blank=True)  # survives actor deletion / api keys
    action = models.CharField(max_length=100, db_index=True)
    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    target_label = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "cs_audit_log"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["workspace", "created_at"])]

    def __str__(self) -> str:
        return f"{self.action} by {self.actor_label or 'system'}"


class SystemErrorLog(models.Model):
    class Level(models.TextChoices):
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"
        CRITICAL = "critical", "Critical"

    source = models.CharField(max_length=100, db_index=True)  # api | engine | webhooks | ...
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.ERROR)
    message = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    traceback = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "cs_system_error_log"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"[{self.level}] {self.source}: {self.message[:80]}"


class WorkerJobLog(models.Model):
    class Status(models.TextChoices):
        STARTED = "started", "Started"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    task_name = models.CharField(max_length=200, db_index=True)
    task_id = models.CharField(max_length=64, blank=True)
    chain = models.ForeignKey(
        "chains.Chain", null=True, blank=True, on_delete=models.SET_NULL, related_name="worker_logs"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.STARTED)
    detail = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "cs_worker_job_log"
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.task_name} [{self.status}]"
