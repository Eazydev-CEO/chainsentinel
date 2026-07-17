"""Optional WebSocket accelerator (disabled by default).

Subscribes to `newHeads` on chains whose providers expose a WS endpoint and
enqueues `poll_chain` immediately when a head arrives — HTTP polling remains
the primary, reliable path and continues regardless of this process.

Run (only if WS_SUBSCRIPTIONS_ENABLED=true):
    python manage.py listen_ws
"""
import asyncio
import logging

from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger("chainsentinel.ws")

RECONNECT_BASE = 5
RECONNECT_CAP = 300


class Command(BaseCommand):
    help = "Subscribe to newHeads via WebSocket and trigger polls early (optional accelerator)."

    def handle(self, *args, **options):
        if not settings.WS_SUBSCRIPTIONS_ENABLED:
            self.stdout.write(
                "WS_SUBSCRIPTIONS_ENABLED is false — nothing to do. "
                "HTTP polling remains the primary mechanism."
            )
            return

        from apps.chains.models import RpcProvider

        providers = list(
            RpcProvider.objects.filter(is_active=True, chain__is_active=True)
            .exclude(ws_endpoint="")
            .select_related("chain")
        )
        if not providers:
            self.stdout.write("No active providers expose a WebSocket endpoint.")
            return

        self.stdout.write(f"Subscribing to newHeads on {len(providers)} provider(s)…")
        asyncio.run(self._run(providers))

    async def _run(self, providers) -> None:
        await asyncio.gather(*(self._listen_forever(p) for p in providers))

    async def _listen_forever(self, provider) -> None:
        from apps.events.tasks import poll_chain

        backoff = RECONNECT_BASE
        while True:
            try:
                from web3 import AsyncWeb3, WebSocketProvider

                async with AsyncWeb3(WebSocketProvider(provider.ws_endpoint)) as w3:
                    subscription = await w3.eth.subscribe("newHeads")
                    logger.info(
                        "WS subscribed chain=%s provider=%s sub=%s",
                        provider.chain.slug, provider.name, subscription,
                    )
                    backoff = RECONNECT_BASE
                    async for _payload in w3.socket.process_subscriptions():
                        # A new head arrived — poll now instead of waiting for beat.
                        await asyncio.to_thread(poll_chain.delay, provider.chain_id)
            except Exception as exc:  # noqa: BLE001 — reconnect with backoff
                logger.warning(
                    "WS connection lost chain=%s provider=%s (%s). Reconnecting in %ss; "
                    "HTTP polling continues meanwhile.",
                    provider.chain.slug, provider.name, exc, backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, RECONNECT_CAP)
