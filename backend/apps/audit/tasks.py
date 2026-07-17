"""Retention cleanup — keeps the operational tables lean."""
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone


@shared_task(name="apps.audit.tasks.cleanup_old_records")
def cleanup_old_records() -> dict:
    """Delete records past their retention windows (batched, idempotent)."""
    from apps.audit.models import SystemErrorLog, WorkerJobLog
    from apps.chains.models import RpcProviderHealthLog
    from apps.events.models import BlockchainEvent
    from apps.notifications.models import Notification
    from apps.webhooks.models import WebhookDelivery

    from .services import job_log

    now = timezone.now()
    deleted: dict[str, int] = {}

    with job_log("cleanup_old_records"):
        plans = [
            (
                BlockchainEvent,
                {"created_at__lt": now - timedelta(days=settings.RETENTION_EVENTS_DAYS)},
                "events",
            ),
            (
                WebhookDelivery,
                {"created_at__lt": now - timedelta(days=settings.RETENTION_WEBHOOK_DELIVERIES_DAYS)},
                "webhook_deliveries",
            ),
            (
                RpcProviderHealthLog,
                {"checked_at__lt": now - timedelta(days=settings.RETENTION_HEALTH_LOGS_DAYS)},
                "health_logs",
            ),
            (
                WorkerJobLog,
                {"started_at__lt": now - timedelta(days=settings.RETENTION_WORKER_LOGS_DAYS)},
                "worker_logs",
            ),
            (
                SystemErrorLog,
                {"created_at__lt": now - timedelta(days=90)},
                "system_errors",
            ),
            (
                Notification,
                {
                    "created_at__lt": now - timedelta(days=60),
                    "read_at__isnull": False,
                },
                "read_notifications",
            ),
        ]
        for model, filters, label in plans:
            total = 0
            while True:  # batched deletes — avoid one giant transaction
                ids = list(model.objects.filter(**filters).values_list("pk", flat=True)[:2000])
                if not ids:
                    break
                count, _ = model.objects.filter(pk__in=ids).delete()
                total += count
            deleted[label] = total

    return deleted
