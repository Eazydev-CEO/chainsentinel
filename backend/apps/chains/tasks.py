"""Provider health monitoring."""
import logging
import time

from celery import shared_task
from django.conf import settings
from django.core.cache import cache

from apps.audit.services import job_log, log_system_error

logger = logging.getLogger("chainsentinel.chains")

OUTAGE_FLAG_TTL = 6 * 3600


@shared_task(name="apps.chains.tasks.check_provider_health")
def check_provider_health() -> dict:
    """Probe every active provider; log health; raise outage notifications."""
    from .client import classify_exception, default_web3_factory
    from .models import Chain, RpcProvider, RpcProviderHealthLog

    results: dict[str, str] = {}

    with job_log("check_provider_health"):
        providers = RpcProvider.objects.filter(is_active=True, chain__is_active=True).select_related(
            "chain"
        )
        for provider in providers:
            started = time.monotonic()
            try:
                w3 = default_web3_factory(provider)
                block_number = int(w3.eth.block_number)
                latency_ms = int((time.monotonic() - started) * 1000)
                RpcProviderHealthLog.objects.create(
                    provider=provider, ok=True, latency_ms=latency_ms, block_number=block_number
                )
                provider.record_success(latency_ms)
                results[str(provider)] = "ok"
            except Exception as exc:  # noqa: BLE001
                reason = classify_exception(exc)
                RpcProviderHealthLog.objects.create(provider=provider, ok=False, error=reason[:500])
                provider.record_failure(
                    reason, unhealthy_threshold=settings.ENGINE_PROVIDER_FAILURE_THRESHOLD
                )
                results[str(provider)] = reason

        # Chain-level outage detection: all active providers unhealthy.
        for chain in Chain.objects.filter(is_active=True):
            active = [p for p in providers if p.chain_id == chain.pk]
            if not active:
                continue
            all_down = all(
                p.health_status == RpcProvider.HealthStatus.UNHEALTHY for p in active
            )
            flag_key = f"chain:outage:{chain.pk}"
            if all_down and cache.add(flag_key, "1", timeout=OUTAGE_FLAG_TTL):
                _notify_chain_outage(chain)
            elif not all_down:
                cache.delete(flag_key)

    return results


def _notify_chain_outage(chain) -> None:
    """One-time (per window) notification that a chain has no healthy providers."""
    from apps.monitors.models import ContractMonitor, WalletMonitor
    from apps.notifications.services import notify_workspace, send_platform_alert
    from apps.workspaces.models import Workspace

    log_system_error(
        source="chains",
        level="critical",
        message=f"All RPC providers unhealthy for chain {chain.slug}",
        details={"chain": chain.slug, "chain_id": chain.chain_id},
    )
    send_platform_alert(
        subject=f"[ChainSentinel] RPC outage on {chain.name}",
        template="provider_outage",
        context={"chain": chain},
    )

    workspace_ids = set(
        WalletMonitor.objects.filter(chain=chain, is_active=True).values_list("workspace_id", flat=True)
    ) | set(
        ContractMonitor.objects.filter(chain=chain, is_active=True).values_list("workspace_id", flat=True)
    )
    for workspace in Workspace.objects.filter(pk__in=workspace_ids):
        notify_workspace(
            workspace=workspace,
            type="provider_outage",
            severity="high",
            title=f"RPC outage on {chain.name}",
            body=(
                f"All RPC providers for {chain.name} are currently failing. "
                "Monitoring on this chain is paused until a provider recovers."
            ),
            link="/app/providers",
            email_template="provider_outage",
            email_context={"chain": chain},
        )
