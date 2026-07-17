import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

DEMO_WALLET = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
OTHER_WALLET = "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B"
TOKEN_ADDRESS = "0x7169D38820dfd117C3FA1f22a697dBA58d90BA06"
SPENDER = "0x1111111254EEB25477B68fb85Ed929f73A960582"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def user(db):
    from apps.accounts.models import User, UserProfile

    user = User.objects.create_user(
        email="owner@example.com", password="Str0ngPass!123", first_name="Olive", last_name="Owner"
    )
    user.is_email_verified = True
    user.save()
    UserProfile.objects.create(user=user)
    return user


@pytest.fixture
def workspace(user):
    from apps.workspaces.services import create_workspace

    return create_workspace(name="Test Workspace", owner=user)


@pytest.fixture
def chain(db):
    from apps.chains.models import Chain

    return Chain.objects.create(
        name="Testnet",
        slug="testnet",
        chain_id=31337,
        native_symbol="ETH",
        explorer_url="https://explorer.test",
        is_testnet=True,
        is_active=True,
        required_confirmations=2,
        block_time_seconds=2.0,
    )


@pytest.fixture
def provider(chain):
    from apps.chains.models import RpcProvider

    return RpcProvider.objects.create(
        chain=chain,
        name="primary",
        http_endpoint="https://rpc-primary.invalid",
        priority=10,
        is_active=True,
        rate_limit_per_second=100,
    )


@pytest.fixture
def wallet_monitor(workspace, chain, user):
    from apps.monitors.models import WalletMonitor

    return WalletMonitor.objects.create(
        workspace=workspace,
        chain=chain,
        name="Treasury",
        address=DEMO_WALLET,
        direction="both",
        event_types=["native_transfer", "erc20_transfer", "nft_transfer", "approval"],
        severity="medium",
        created_by=user,
        large_tx_threshold_wei=10**18,  # 1 ETH
    )


@pytest.fixture
def api(user, workspace):
    """Authenticated API client bound to `user` (auth mechanics bypassed)."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def member_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def make_user(db):
    from apps.accounts.models import User

    def _make(email: str, *, verified: bool = True):
        member = User.objects.create_user(email=email, password="Str0ngPass!123")
        if verified:
            member.is_email_verified = True
            member.save()
        return member

    return _make


@pytest.fixture
def add_member(workspace):
    from apps.workspaces.models import WorkspaceMember

    def _add(user, role: str):
        return WorkspaceMember.objects.create(workspace=workspace, user=user, role=role)

    return _add
