from celery import shared_task


@shared_task(name="apps.alerts.tasks.evaluate_event_alerts", max_retries=3, default_retry_delay=30)
def evaluate_event_alerts(event_id: int) -> dict:
    """Evaluate all workspace rules against one event (idempotent)."""
    from apps.events.models import BlockchainEvent

    from .services import evaluate_event

    try:
        event = BlockchainEvent.objects.select_related(
            "chain", "workspace", "wallet_monitor", "contract_monitor"
        ).get(pk=event_id)
    except BlockchainEvent.DoesNotExist:
        return {"skipped": "event missing"}

    alerts = evaluate_event(event)
    return {"event": event_id, "alerts_created": len(alerts)}
