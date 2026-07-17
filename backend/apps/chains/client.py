"""Responsible RPC failover client.

Walks a chain's providers in priority order. On timeout / connection error /
rate-limit / invalid response it records the failure, puts the provider into
an exponential-backoff window (Redis), and moves to the next provider.

It deliberately does NOT rotate proxies, spoof identities, or otherwise try
to evade provider restrictions — failures are respected, logged, and backed
off.
"""
import logging
import time

import requests
from django.conf import settings
from django.core.cache import cache
from web3 import Web3
from web3.exceptions import Web3Exception

from .models import Chain, RpcProvider

logger = logging.getLogger("chainsentinel.rpc")


class RpcError(Exception):
    """Base error for RPC access problems."""


class AllProvidersFailedError(RpcError):
    def __init__(self, chain_slug: str, errors: list[str]):
        self.errors = errors
        super().__init__(f"All RPC providers failed for {chain_slug}: {'; '.join(errors) or 'none available'}")


def default_web3_factory(provider: RpcProvider) -> Web3:
    return Web3(
        Web3.HTTPProvider(
            provider.http_endpoint,
            request_kwargs={"timeout": settings.ENGINE_RPC_TIMEOUT_SECONDS},
        )
    )


def classify_exception(exc: Exception) -> str:
    if isinstance(exc, requests.exceptions.Timeout):
        return "timeout"
    if isinstance(exc, requests.exceptions.HTTPError):
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status == 429:
            return "rate_limited"
        return f"http_{status or 'error'}"
    if isinstance(exc, requests.exceptions.ConnectionError):
        return "connection_error"
    if isinstance(exc, Web3Exception):
        return f"rpc_error:{exc.__class__.__name__}"
    if isinstance(exc, (ValueError, KeyError, TypeError)):
        return f"invalid_response:{exc.__class__.__name__}"
    return f"unexpected:{exc.__class__.__name__}"


class RpcClient:
    """Failover-aware RPC access for one chain."""

    def __init__(self, chain: Chain, providers=None, web3_factory=None):
        self.chain = chain
        self._providers = providers
        self.web3_factory = web3_factory or default_web3_factory
        self._w3_instances: dict[int, Web3] = {}

    # -- provider selection --------------------------------------------------
    @property
    def providers(self) -> list[RpcProvider]:
        if self._providers is None:
            self._providers = list(
                RpcProvider.objects.filter(chain=self.chain, is_active=True).order_by("priority")
            )
        return self._providers

    def _backoff_key(self, provider: RpcProvider) -> str:
        return f"rpc:backoff:{provider.pk}"

    def _in_backoff(self, provider: RpcProvider) -> bool:
        return cache.get(self._backoff_key(provider)) is not None

    def _set_backoff(self, provider: RpcProvider) -> None:
        base = settings.ENGINE_PROVIDER_BACKOFF_BASE
        cap = settings.ENGINE_PROVIDER_BACKOFF_CAP
        seconds = min(base * (2 ** max(provider.consecutive_failures - 1, 0)), cap)
        cache.set(self._backoff_key(provider), "1", timeout=seconds)

    def _clear_backoff(self, provider: RpcProvider) -> None:
        cache.delete(self._backoff_key(provider))

    def _rate_limit_ok(self, provider: RpcProvider) -> bool:
        """Local token counter per second so we respect the provider's limits."""
        limit = provider.rate_limit_per_second or 10
        key = f"rpc:rl:{provider.pk}:{int(time.time())}"
        added = cache.add(key, 1, timeout=2)
        if added:
            return True
        try:
            current = cache.incr(key)
        except ValueError:  # key expired between add and incr
            return True
        return current <= limit

    # -- invocation ----------------------------------------------------------
    def _w3(self, provider: RpcProvider) -> Web3:
        key = provider.pk or id(provider)
        if key not in self._w3_instances:
            self._w3_instances[key] = self.web3_factory(provider)
        return self._w3_instances[key]

    @staticmethod
    def _invoke(w3: Web3, method: str, *args, **kwargs):
        if method == "block_number":
            return w3.eth.block_number
        if method == "chain_id":
            return w3.eth.chain_id
        if method == "get_block":
            return w3.eth.get_block(*args, **kwargs)
        if method == "get_logs":
            return w3.eth.get_logs(*args, **kwargs)
        if method == "get_transaction_receipt":
            return w3.eth.get_transaction_receipt(*args, **kwargs)
        if method == "eth_call":
            return w3.eth.call(*args, **kwargs)
        raise ValueError(f"Unsupported RPC method wrapper: {method}")

    def call(self, method: str, *args, **kwargs):
        """Invoke `method` with failover across providers."""
        errors: list[str] = []
        attempted = 0

        for provider in self.providers:
            if self._in_backoff(provider):
                errors.append(f"{provider.name}: in backoff window")
                continue
            if not self._rate_limit_ok(provider):
                errors.append(f"{provider.name}: local rate limit reached")
                continue

            attempted += 1
            started = time.monotonic()
            try:
                result = self._invoke(self._w3(provider), method, *args, **kwargs)
            except Exception as exc:  # noqa: BLE001 — classified below
                reason = classify_exception(exc)
                provider.record_failure(
                    reason, unhealthy_threshold=settings.ENGINE_PROVIDER_FAILURE_THRESHOLD
                )
                self._set_backoff(provider)
                errors.append(f"{provider.name}: {reason}")
                logger.warning(
                    "RPC failure chain=%s provider=%s method=%s reason=%s",
                    self.chain.slug,
                    provider.name,
                    method,
                    reason,
                )
                continue

            latency_ms = int((time.monotonic() - started) * 1000)
            provider.record_success(latency_ms)
            self._clear_backoff(provider)
            return result

        raise AllProvidersFailedError(self.chain.slug, errors)

    # -- convenience wrappers --------------------------------------------
    def get_block_number(self) -> int:
        return int(self.call("block_number"))

    def get_block(self, block_identifier, full_transactions: bool = False):
        return self.call("get_block", block_identifier, full_transactions=full_transactions)

    def get_logs(self, params: dict):
        return self.call("get_logs", params)

    def eth_call(self, tx: dict):
        return self.call("eth_call", tx)
