"""Email delivery + daily digests."""
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

logger = logging.getLogger("chainsentinel.notifications")


@shared_task(
    name="apps.notifications.tasks.send_email_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_email_task(self, *, subject: str, to: list[str], text: str, html: str = "") -> dict:
    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=to,
        )
        if html:
            message.attach_alternative(html, "text/html")
        message.send()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Email send failed (%s) — retrying: %s", subject, exc)
        raise self.retry(exc=exc)
    return {"sent": len(to)}


@shared_task(name="apps.notifications.tasks.send_daily_summaries")
def send_daily_summaries() -> dict:
    """Per-workspace daily digest to members who opted in."""
    from django.db.models import Count

    from apps.alerts.models import Alert
    from apps.audit.services import job_log
    from apps.events.models import BlockchainEvent
    from apps.webhooks.models import WebhookDelivery
    from apps.workspaces.models import Workspace

    from .emails import send_templated_email
    from .models import NotificationPreference

    since = timezone.now() - timedelta(hours=24)
    sent = 0

    with job_log("send_daily_summaries"):
        for workspace in Workspace.objects.filter(suspended_at__isnull=True):
            recipients = [
                member.user.email
                for member in workspace.members.select_related("user")
                if member.user.is_active
                and member.user.is_email_verified
                and NotificationPreference.for_user(member.user).email_daily_summary
            ]
            if not recipients:
                continue

            events = BlockchainEvent.objects.filter(workspace=workspace, created_at__gte=since)
            alerts = Alert.objects.filter(workspace=workspace, created_at__gte=since)
            deliveries = WebhookDelivery.objects.filter(workspace=workspace, created_at__gte=since)
            if not events.exists() and not alerts.exists():
                continue  # nothing to report

            severity_counts = dict(
                alerts.values_list("severity").annotate(count=Count("id")).order_by()
            )
            delivered_ok = deliveries.filter(status="success").count()
            context = {
                "workspace": workspace,
                "events_count": events.count(),
                "alerts_count": alerts.count(),
                "critical_count": severity_counts.get("critical", 0),
                "high_count": severity_counts.get("high", 0),
                "webhook_total": deliveries.count(),
                "webhook_ok": delivered_ok,
            }
            send_templated_email(
                to=recipients,
                subject=f"[ChainSentinel] Daily summary — {workspace.name}",
                template="daily_summary",
                context=context,
            )
            sent += 1
    return {"workspaces": sent}
