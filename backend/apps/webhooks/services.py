"""Webhook dispatch — creating deliveries and enqueueing the delivery task."""
import logging

from .models import WebhookDelivery, WebhookEndpoint

logger = logging.getLogger("chainsentinel.webhooks")


def _enqueue(delivery: WebhookDelivery) -> None:
    from .tasks import deliver_webhook

    deliver_webhook.delay(delivery.pk)


def create_delivery(
    *, endpoint: WebhookEndpoint, event_type: str, data: dict, idempotency_key: str,
    replay_of: WebhookDelivery | None = None,
) -> WebhookDelivery | None:
    """Idempotently create a delivery and enqueue it. Returns None if it already exists."""
    delivery, created = WebhookDelivery.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults={
            "endpoint": endpoint,
            "workspace": endpoint.workspace,
            "event_type": event_type,
            "payload": data,
            "max_attempts": min(endpoint.max_retries or 5, 10),
            "replay_of": replay_of,
        },
    )
    if not created:
        return None
    _enqueue(delivery)
    return delivery


def dispatch_workspace_event(*, workspace, event_type: str, data: dict, idempotency_suffix: str) -> int:
    """Fan an event out to every enabled endpoint subscribed to its type."""
    endpoints = WebhookEndpoint.objects.filter(workspace=workspace, enabled=True)
    count = 0
    for endpoint in endpoints:
        if not endpoint.subscribes_to(event_type):
            continue
        delivery = create_delivery(
            endpoint=endpoint,
            event_type=event_type,
            data=data,
            idempotency_key=f"ep:{endpoint.pk}:{idempotency_suffix}",
        )
        if delivery:
            count += 1
    return count


def dispatch_alert_webhook(*, rule, alert, event) -> int:
    """Deliver alert.triggered — to the rule's endpoint, or all subscribed ones."""
    payload = {
        "alert_id": alert.pk,
        "title": alert.title,
        "message": alert.message,
        "severity": alert.severity,
        "status": alert.status,
        "rule": {"id": rule.pk, "name": rule.name},
        "event": {
            "id": event.pk,
            "event_type": event.event_type,
            "chain": event.chain.slug,
            "tx_hash": event.tx_hash,
            "block_number": event.block_number,
            "from_address": event.from_address,
            "to_address": event.to_address,
            "spender_address": event.spender_address,
            "token_address": event.token_address,
            "token_symbol": event.token_symbol,
            "amount_wei": str(event.amount_wei) if event.amount_wei is not None else None,
            "is_large": event.is_large,
        },
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }

    if rule.webhook_id:
        endpoint = rule.webhook
        if endpoint is None or not endpoint.enabled:
            return 0
        delivery = create_delivery(
            endpoint=endpoint,
            event_type="alert.triggered",
            data=payload,
            idempotency_key=f"ep:{endpoint.pk}:alert:{alert.pk}:triggered",
        )
        return 1 if delivery else 0

    return dispatch_workspace_event(
        workspace=alert.workspace,
        event_type="alert.triggered",
        data=payload,
        idempotency_suffix=f"alert:{alert.pk}:triggered",
    )
