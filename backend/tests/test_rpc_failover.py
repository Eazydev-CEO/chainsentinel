"""RPC provider failover: retries, backoff, health tracking, rate limits."""
import pytest
import requests

from apps.chains.client import AllProvidersFailedError, RpcClient, classify_exception
from apps.chains.models import RpcProvider

from .fakes import FailingWeb3, FakeChainData, FakeWeb3

pytestmark = pytest.mark.django_db


@pytest.fixture
def providers(chain):
    primary = RpcProvider.objects.create(
        chain=chain, name="primary", http_endpoint="https://primary.invalid",
        priority=10, is_active=True, rate_limit_per_second=100,
    )
    fallback = RpcProvider.objects.create(
        chain=chain, name="fallback", http_endpoint="https://fallback.invalid",
        priority=20, is_active=True, rate_limit_per_second=100,
    )
    return primary, fallback


def _client(chain, providers, fakes: dict):
    return RpcClient(
        chain,
        providers=list(providers),
        web3_factory=lambda provider: fakes[provider.name],
    )


def _make_429() -> requests.exceptions.HTTPError:
    response = requests.Response()
    response.status_code = 429
    return requests.exceptions.HTTPError(response=response)


class TestFailover:
    def test_timeout_fails_over_to_next_provider(self, chain, providers):
        primary, fallback = providers
        data = FakeChainData()
        data.add_block(42)
        fakes = {
            "primary": FailingWeb3(requests.exceptions.Timeout("boom")),
            "fallback": FakeWeb3(data),
        }
        client = _client(chain, providers, fakes)

        assert client.get_block_number() == 42

        primary.refresh_from_db()
        fallback.refresh_from_db()
        assert primary.consecutive_failures == 1
        assert primary.health_status == RpcProvider.HealthStatus.DEGRADED
        assert primary.last_failure_reason == "timeout"
        assert fallback.health_status == RpcProvider.HealthStatus.HEALTHY
        assert fallback.last_success_at is not None

    def test_rate_limit_response_classified_and_failed_over(self, chain, providers):
        data = FakeChainData()
        data.add_block(7)
        fakes = {"primary": FailingWeb3(_make_429()), "fallback": FakeWeb3(data)}
        client = _client(chain, providers, fakes)

        assert client.get_block_number() == 7
        providers[0].refresh_from_db()
        assert providers[0].last_failure_reason == "rate_limited"

    def test_invalid_response_fails_over(self, chain, providers):
        data = FakeChainData()
        data.add_block(9)
        fakes = {"primary": FailingWeb3(ValueError("garbage")), "fallback": FakeWeb3(data)}
        client = _client(chain, providers, fakes)
        assert client.get_block_number() == 9
        providers[0].refresh_from_db()
        assert providers[0].last_failure_reason.startswith("invalid_response")

    def test_all_providers_failing_raises(self, chain, providers):
        fakes = {
            "primary": FailingWeb3(requests.exceptions.ConnectionError("down")),
            "fallback": FailingWeb3(requests.exceptions.Timeout("slow")),
        }
        client = _client(chain, providers, fakes)
        with pytest.raises(AllProvidersFailedError) as excinfo:
            client.get_block_number()
        assert "primary" in str(excinfo.value)
        assert "fallback" in str(excinfo.value)

    def test_backoff_skips_failed_provider_on_next_call(self, chain, providers):
        data = FakeChainData()
        data.add_block(5)
        failing = FailingWeb3(requests.exceptions.Timeout("boom"))
        fakes = {"primary": failing, "fallback": FakeWeb3(data)}
        client = _client(chain, providers, fakes)

        client.get_block_number()
        attempts_after_first = failing.eth.attempts
        assert attempts_after_first == 1

        # Second call: primary is inside its backoff window — not even tried.
        client.get_block_number()
        assert failing.eth.attempts == attempts_after_first

    def test_unhealthy_after_threshold(self, chain, providers, settings):
        settings.ENGINE_PROVIDER_FAILURE_THRESHOLD = 2
        primary, _ = providers
        data = FakeChainData()
        data.add_block(1)
        failing = FailingWeb3(requests.exceptions.Timeout("boom"))
        fakes = {"primary": failing, "fallback": FakeWeb3(data)}

        from django.core.cache import cache

        for _ in range(2):
            _client(chain, providers, fakes).get_block_number()
            cache.clear()  # lift the backoff so the next call retries primary

        primary.refresh_from_db()
        assert primary.consecutive_failures == 2
        assert primary.health_status == RpcProvider.HealthStatus.UNHEALTHY

    def test_success_resets_failure_counters(self, chain, providers):
        primary, _ = providers
        primary.record_failure("timeout")
        assert primary.consecutive_failures == 1

        data = FakeChainData()
        data.add_block(3)
        fakes = {"primary": FakeWeb3(data), "fallback": FakeWeb3(data)}
        _client(chain, providers, fakes).get_block_number()

        primary.refresh_from_db()
        assert primary.consecutive_failures == 0
        assert primary.health_status == RpcProvider.HealthStatus.HEALTHY

    def test_local_rate_limit_skips_provider(self, chain, providers):
        primary, fallback = providers
        primary.rate_limit_per_second = 1
        primary.save()
        data = FakeChainData()
        data.add_block(11)
        primary_fake, fallback_fake = FakeWeb3(data), FakeWeb3(data)
        client = _client(chain, providers, {"primary": primary_fake, "fallback": fallback_fake})

        results = [client.get_block_number() for _ in range(4)]
        assert results == [11, 11, 11, 11]
        # Overflow calls were served by the fallback, not hammered at primary.
        assert any(call[0] == "block_number" for call in fallback_fake.eth.calls)


class TestClassification:
    @pytest.mark.parametrize(
        "exc,expected",
        [
            (requests.exceptions.Timeout(), "timeout"),
            (requests.exceptions.ConnectionError(), "connection_error"),
            (_make_429(), "rate_limited"),
            (ValueError("x"), "invalid_response:ValueError"),
            (RuntimeError("x"), "unexpected:RuntimeError"),
        ],
    )
    def test_classify(self, exc, expected):
        assert classify_exception(exc) == expected
