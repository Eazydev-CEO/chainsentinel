"""Engine Celery tasks: scheduling, polling, confirmation."""
import logging

from celery import shared_task
from django.core.cache import cache
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger("chainsentinel.engine")

RPC_FAILURE_NOTICE_TTL = 900  # only log one all-providers-down error per chain / 15 min


@shared_task(name="apps.events.tasks.schedule_chain_polls")
def schedule_chain_polls() -> list[str]:
    """Enqueue a poll task for every active chain that has active monitors."""
    from apps.chains.models import Chain
    from apps.monitors.models import ContractMonitor, WalletMonitor

    scheduled = []
    wallet_chains = set(
        WalletMonitor.objects.filter(
            is_active=True, workspace__suspended_at__isnull=True
        ).values_list("chain_id", flat=True)
    )
    contract_chains = set(
        ContractMonitor.objects.filter(
            is_active=True, workspace__suspended_at__isnull=True
        ).values_list("chain_id", flat=True)
    )
    for chain in Chain.objects.filter(is_active=True, pk__in=wallet_chains | contract_chains):
        poll_chain.delay(chain.pk)
        scheduled.append(chain.slug)
    return scheduled


@shared_task(
    name="apps.events.tasks.poll_chain",
    bind=True,
    max_retries=0,  # the beat scheduler re-enqueues; no retry storms
    soft_time_limit=240,
    time_limit=280,
)
def poll_chain(self, chain_id: int) -> dict:
    """Poll one chain for new blocks (single-flight via Redis lock)."""
    from apps.audit.services import job_log, log_system_error
    from apps.chains.client import AllProvidersFailedError
    from apps.chains.models import Chain, RpcProvider

    from .engine import ChainEngine, chain_poll_lock

    try:
        chain = Chain.objects.get(pk=chain_id, is_active=True)
    except Chain.DoesNotExist:
        return {"skipped": "chain inactive or missing"}

    # No usable endpoint → skip quietly (placeholder providers stay inactive).
    # Provider *failures* still surface loudly via AllProvidersFailedError below.
    if not RpcProvider.objects.filter(chain=chain, is_active=True).exists():
        return {"skipped": "no active RPC providers configured"}

    with chain_poll_lock(chain_id) as acquired:
        if not acquired:
            return {"skipped": "another worker holds the poll lock"}

        engine = ChainEngine(chain)
        if not engine.has_work:
            return {"skipped": "no active monitors"}

        with job_log("poll_chain", task_id=str(self.request.id or ""), chain=chain) as entry:
            try:
                stats = engine.poll()
            except AllProvidersFailedError as exc:
                notice_key = f"rpcfail:notice:{chain_id}"
                if cache.add(notice_key, "1", timeout=RPC_FAILURE_NOTICE_TTL):
                    log_system_error(
                        source="engine",
                        message=f"Polling failed — all providers down for {chain.slug}",
                        details={"errors": exc.errors[:10]},
                    )
                entry.detail = {"error": "all_providers_failed"}
                raise
            entry.detail = stats

        if stats.get("events"):
            confirm_pending_events.delay(chain_id)
        return stats


@shared_task(name="apps.events.tasks.confirm_pending_events")
def confirm_pending_events(chain_id: int | None = None) -> dict:
    """Promote PENDING events to CONFIRMED once their depth is reached,
    then hand them to the alert engine and webhook dispatch."""
    from apps.alerts.tasks import evaluate_event_alerts
    from apps.chains.client import AllProvidersFailedError, RpcClient
    from apps.chains.models import Chain
    from apps.webhooks.services import dispatch_workspace_event

    from .models import BlockchainEvent, EventStatus

    chains = Chain.objects.filter(is_active=True)
    if chain_id is not None:
        chains = chains.filter(pk=chain_id)

    confirmed_total = 0
    for chain in chains:
        pending_exists = BlockchainEvent.objects.filter(
            chain=chain, status=EventStatus.PENDING
        ).exists()
        if not pending_exists:
            continue
        try:
            latest = RpcClient(chain).get_block_number()
        except AllProvidersFailedError:
            continue  # try again next beat tick

        ready = BlockchainEvent.objects.filter(
            chain=chain,
            status=EventStatus.PENDING,
            block_number__lte=latest + 1 - F("confirmations_required"),
        ).select_related("workspace", "chain")[:500]

        now = timezone.now()
        for event in ready:
            # Idempotent promotion: only the transition PENDING→CONFIRMED fires actions.
            updated = BlockchainEvent.objects.filter(
                pk=event.pk, status=EventStatus.PENDING
            ).update(status=EventStatus.CONFIRMED, confirmed_at=now)
            if not updated:
                continue
            confirmed_total += 1
            evaluate_event_alerts.delay(event.pk)
            dispatch_workspace_event(
                workspace=event.workspace,
                event_type="event.confirmed",
                data=_webhook_event_payload(event),
                idempotency_suffix=f"event:{event.pk}:confirmed",
            )

    return {"confirmed": confirmed_total}


def _webhook_event_payload(event) -> dict:
    return {
        "event_id": event.pk,
        "event_type": event.event_type,
        "chain": event.chain.slug,
        "block_number": event.block_number,
        "tx_hash": event.tx_hash,
        "log_index": event.log_index,
        "from_address": event.from_address,
        "to_address": event.to_address,
        "spender_address": event.spender_address,
        "token_address": event.token_address,
        "token_symbol": event.token_symbol,
        "amount_wei": str(event.amount_wei) if event.amount_wei is not None else None,
        "is_large": event.is_large,
        "severity": event.severity,
        "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
        "monitor": {
            "kind": "wallet" if event.wallet_monitor_id else "contract",
            "id": event.wallet_monitor_id or event.contract_monitor_id,
        },
    }


@shared_task(name="apps.events.tasks.reprocess_event_alerts")
def reprocess_event_alerts(event_id: int) -> dict:
    """Admin action: re-run alert evaluation for a confirmed event."""
    from apps.alerts.tasks import evaluate_event_alerts

    evaluate_event_alerts.delay(event_id)
    return {"requeued": event_id}
