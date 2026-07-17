"""Webhook delivery worker: HMAC signing, SSRF guard, exponential retries."""
import json
import logging
import time
from datetime import timedelta

import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .signer import signature_header
from .ssrf import WebhookSecurityError, validate_webhook_url

logger = logging.getLogger("chainsentinel.webhooks")


def _classify_failure(exc: Exception) -> str:
    if isinstance(exc, requests.exceptions.Timeout):
        return "timeout"
    if isinstance(exc, requests.exceptions.SSLError):
        return "tls_error"
    if isinstance(exc, requests.exceptions.ConnectionError):
        return "connection_error"
    return f"error:{exc.__class__.__name__}"


@shared_task(name="apps.webhooks.tasks.deliver_webhook", bind=True, max_retries=0)
def deliver_webhook(self, delivery_id: int) -> dict:
    """Attempt one delivery. Retries are scheduled via `next_retry_at` +
    the beat scanner (survives worker restarts, unlike countdown chains)."""
    from .models import WebhookDelivery

    try:
        delivery = WebhookDelivery.objects.select_related(
            "endpoint", "workspace"
        ).get(pk=delivery_id)
    except WebhookDelivery.DoesNotExist:
        return {"skipped": "delivery missing"}

    if delivery.status in (WebhookDelivery.Status.SUCCESS, WebhookDelivery.Status.EXHAUSTED):
        return {"skipped": f"already {delivery.status}"}

    endpoint = delivery.endpoint
    if not endpoint.enabled:
        _mark_exhausted(delivery, "endpoint disabled")
        return {"failed": "endpoint disabled"}

    body = json.dumps(
        {
            "id": delivery.idempotency_key,
            "type": delivery.event_type,
            "created_at": delivery.created_at.isoformat(),
            "workspace_id": delivery.workspace_id,
            "data": delivery.payload,
        },
        separators=(",", ":"),
        default=str,
    )
    timestamp = int(time.time())

    delivery.attempt_count += 1

    # SSRF validation happens at send time too — DNS may have changed.
    try:
        validate_webhook_url(endpoint.url)
    except WebhookSecurityError as exc:
        _record_failure(delivery, endpoint, f"blocked: {exc}", response_status=None)
        return {"failed": str(exc)}

    try:
        secret = endpoint.get_secret()
    except ValueError as exc:
        _record_failure(delivery, endpoint, str(exc)[:200], response_status=None)
        return {"failed": "secret unavailable"}

    headers = {
        "Content-Type": "application/json",
        "User-Agent": settings.WEBHOOK_USER_AGENT,
        "X-ChainSentinel-Event": delivery.event_type,
        "X-ChainSentinel-Delivery": delivery.idempotency_key,
        "X-ChainSentinel-Timestamp": str(timestamp),
        "X-ChainSentinel-Signature": signature_header(secret, timestamp, body),
    }

    started = time.monotonic()
    try:
        response = requests.post(
            endpoint.url,
            data=body.encode(),
            headers=headers,
            timeout=min(endpoint.timeout_seconds or settings.WEBHOOK_DEFAULT_TIMEOUT, 30),
            allow_redirects=False,  # redirects could bypass the SSRF check
        )
    except Exception as exc:  # noqa: BLE001 — classified for the record
        _record_failure(delivery, endpoint, _classify_failure(exc), response_status=None)
        return {"failed": _classify_failure(exc)}

    elapsed_ms = int((time.monotonic() - started) * 1000)

    if 200 <= response.status_code < 300:
        delivery.status = WebhookDelivery.Status.SUCCESS
        delivery.response_status = response.status_code
        delivery.response_time_ms = elapsed_ms
        delivery.failure_reason = ""
        delivery.delivered_at = timezone.now()
        delivery.next_retry_at = None
        delivery.save()
        endpoint.last_status = "success"
        endpoint.last_success_at = delivery.delivered_at
        endpoint.last_failure_reason = ""
        endpoint.save(update_fields=["last_status", "last_success_at", "last_failure_reason", "updated_at"])
        return {"success": response.status_code, "ms": elapsed_ms}

    if 300 <= response.status_code < 400:
        reason = f"redirect_{response.status_code}_not_followed"
    else:
        reason = f"http_{response.status_code}"
    _record_failure(delivery, endpoint, reason, response_status=response.status_code, elapsed_ms=elapsed_ms)
    return {"failed": reason}


def _record_failure(delivery, endpoint, reason: str, *, response_status, elapsed_ms=None) -> None:
    from .models import WebhookDelivery

    delivery.response_status = response_status
    delivery.response_time_ms = elapsed_ms
    delivery.failure_reason = reason[:500]

    if delivery.attempt_count >= delivery.max_attempts:
        _mark_exhausted(delivery, reason)
    else:
        backoff = min(
            settings.WEBHOOK_BACKOFF_BASE_SECONDS * (2 ** (delivery.attempt_count - 1)),
            settings.WEBHOOK_BACKOFF_CAP_SECONDS,
        )
        delivery.status = WebhookDelivery.Status.RETRYING
        delivery.next_retry_at = timezone.now() + timedelta(seconds=backoff)
        delivery.save()

    endpoint.last_status = "failed"
    endpoint.last_failure_reason = reason[:500]
    endpoint.save(update_fields=["last_status", "last_failure_reason", "updated_at"])


def _mark_exhausted(delivery, reason: str) -> None:
    from apps.notifications.services import notify_workspace

    from .models import WebhookDelivery

    delivery.status = WebhookDelivery.Status.EXHAUSTED
    delivery.failure_reason = reason[:500]
    delivery.next_retry_at = None
    delivery.save()

    # Don't spam: only notify for real event deliveries, not test pings.
    if delivery.event_type == "test.ping":
        return
    notify_workspace(
        workspace=delivery.workspace,
        type="webhook_failed",
        severity="high",
        title=f"Webhook '{delivery.endpoint.name}' is failing",
        body=(
            f"Delivery of {delivery.event_type} to {delivery.endpoint.url} failed "
            f"{delivery.attempt_count} time(s) and gave up. Last error: {reason}."
        ),
        link="/app/webhooks",
        email_template="webhook_failed",
        email_context={"delivery": delivery, "endpoint": delivery.endpoint},
        email_pref_field="email_failed_webhooks",
    )


@shared_task(name="apps.webhooks.tasks.retry_due_deliveries")
def retry_due_deliveries() -> dict:
    """Beat scanner: re-enqueue deliveries whose backoff has elapsed.
    Also rescues PENDING rows whose original enqueue was lost in a crash."""
    from .models import WebhookDelivery

    now = timezone.now()
    due = WebhookDelivery.objects.filter(
        status=WebhookDelivery.Status.RETRYING, next_retry_at__lte=now
    ).values_list("pk", flat=True)[:200]

    stale_pending = WebhookDelivery.objects.filter(
        status=WebhookDelivery.Status.PENDING,
        attempt_count=0,
        created_at__lte=now - timedelta(minutes=10),
    ).values_list("pk", flat=True)[:200]

    count = 0
    for pk in list(due) + list(stale_pending):
        deliver_webhook.delay(pk)
        count += 1
    return {"requeued": count}
