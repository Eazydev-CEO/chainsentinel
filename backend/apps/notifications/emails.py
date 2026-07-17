"""Templated email sending. Rendering happens in-process; SMTP happens in a
Celery task so HTTP requests never block on a mail server."""
import logging

from django.conf import settings
from django.template.loader import render_to_string

logger = logging.getLogger("chainsentinel.notifications")


def render_email(template: str, context: dict) -> tuple[str, str]:
    base_context = {"frontend_url": settings.FRONTEND_URL, **context}
    text = render_to_string(f"emails/{template}.txt", base_context)
    html = render_to_string(f"emails/{template}.html", base_context)
    return text, html


def send_templated_email(*, to: list[str], subject: str, template: str, context: dict) -> None:
    """Render now, deliver via the worker queue."""
    from .tasks import send_email_task

    if not to:
        return
    try:
        text, html = render_email(template, context)
    except Exception:  # noqa: BLE001 — rendering bugs must not break business flows
        logger.exception("Failed to render email template %s", template)
        return
    send_email_task.delay(subject=subject, to=list(to), text=text, html=html)


def send_platform_alert(*, subject: str, template: str, context: dict) -> None:
    """Operational notice to the platform operators (PLATFORM_ALERT_EMAILS)."""
    recipients = settings.PLATFORM_ALERT_EMAILS
    if recipients:
        send_templated_email(to=recipients, subject=subject, template=template, context=context)
