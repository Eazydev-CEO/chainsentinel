"""Celery application for ChainSentinel background processing."""
import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("chainsentinel")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "schedule-chain-polls": {
        "task": "apps.events.tasks.schedule_chain_polls",
        "schedule": float(os.environ.get("ENGINE_POLL_INTERVAL_SECONDS", "10")),
        "options": {"expires": 30},
    },
    "confirm-pending-events": {
        "task": "apps.events.tasks.confirm_pending_events",
        "schedule": 30.0,
        "options": {"expires": 60},
    },
    "retry-due-webhook-deliveries": {
        "task": "apps.webhooks.tasks.retry_due_deliveries",
        "schedule": 60.0,
        "options": {"expires": 120},
    },
    "check-provider-health": {
        "task": "apps.chains.tasks.check_provider_health",
        "schedule": 60.0,
        "options": {"expires": 120},
    },
    "send-daily-summaries": {
        "task": "apps.notifications.tasks.send_daily_summaries",
        "schedule": crontab(hour=7, minute=0),
    },
    "cleanup-old-records": {
        "task": "apps.audit.tasks.cleanup_old_records",
        "schedule": crontab(hour=3, minute=30),
    },
}
