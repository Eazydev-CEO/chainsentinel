"""Monitoring engine: detection, dedupe, checkpoints, confirmations, reorgs."""
from decimal import Decimal

import pytest

from apps.events.engine import ChainEngine
from apps.events.models import BlockchainEvent, BlockCheckpoint, EventStatus, ReorgIncident

from .conftest import DEMO_WALLET, SPENDER, TOKEN_ADDRESS
from .fakes import (
    APPROVAL_TOPIC,
    TRANSFER_TOPIC,
    FakeChainData,
    MiniClient,
    pad_address,
    pad_uint,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def chain_data():
    data = FakeChainData()
    data.add_block(99)
    data.add_block(100)
    return data


@pytest.fixture
def engine(chain, chain_data, wallet_monitor):
    return ChainEngine(chain, client=MiniClient(chain, chain_data))


def _initialized_engine(chain, chain_data, monitor):
    """Run the first poll (checkpoint anchors at latest-1) and return a fresh engine."""
    engine = ChainEngine(chain, client=MiniClient(chain, chain_data))
    engine.poll()
    return ChainEngine(chain, client=MiniClient(chain, chain_data))


class TestCheckpoint:
    def test_first_poll_initializes_checkpoint_without_backfill(self, chain, engine):
        stats = engine.poll()
        checkpoint = BlockCheckpoint.objects.get(chain=chain)
        assert checkpoint.last_processed_block == 99
        assert stats["initialized_at"] == 99
        assert BlockchainEvent.objects.count() == 0

    def test_checkpoint_advances_and_stores_hash_ring(self, chain, chain_data, wallet_monitor):
        engine = _initialized_engine(chain, chain_data, wallet_monitor)
        chain_data.add_block(101)
        engine.poll()
        checkpoint = BlockCheckpoint.objects.get(chain=chain)
        assert checkpoint.last_processed_block == 101
        numbers = [b["number"] for b in checkpoint.recent_blocks]
        assert numbers == sorted(numbers)
        assert checkpoint.recent_blocks[-1]["hash"] == chain_data.blocks[101]["hash"].lower()


class TestNativeTransfers:
    def test_incoming_native_transfer_detected(self, chain, chain_data, wallet_monitor):
        engine = _initialized_engine(chain, chain_data, wallet_monitor)
        chain_data.add_block(101)
        chain_data.add_tx(101, from_addr="0x" + "33" * 20, to_addr=DEMO_WALLET, value=5 * 10**17)
        stats = engine.poll()

        assert stats["events"] == 1
        event = BlockchainEvent.objects.get()
        assert event.event_type == "native_received"
        assert event.status == EventStatus.PENDING
        assert event.amount_wei == Decimal(5 * 10**17)
        assert event.wallet_monitor_id == wallet_monitor.pk
        assert event.confirmations_required == 2  # chain default

    def test_outgoing_direction_filter(self, chain, chain_data, wallet_monitor):
        wallet_monitor.direction = "outgoing"
        wallet_monitor.save()
        engine = _initialized_engine(chain, chain_data, wallet_monitor)
        chain_data.add_block(101)
        chain_data.add_tx(101, from_addr="0x" + "33" * 20, to_addr=DEMO_WALLET, value=10**18)
        engine.poll()
        assert BlockchainEvent.objects.count() == 0  # incoming tx ignored

    def test_min_value_filter(self, chain, chain_data, wallet_monitor):
        wallet_monitor.min_value_wei = Decimal(10**18)
        wallet_monitor.save()
        engine = _initialized_engine(chain, chain_data, wallet_monitor)
        chain_data.add_block(101)
        chain_data.add_tx(101, from_addr="0x" + "33" * 20, to_addr=DEMO_WALLET, value=10**17)
        engine.poll()
        assert BlockchainEvent.objects.count() == 0

    def test_large_transfer_flag_and_severity_bump(self, chain, chain_data, wallet_monitor):
        engine = _initialized_engine(chain, chain_data, wallet_monitor)
        chain_data.add_block(101)
        chain_data.add_tx(101, from_addr=DEMO_WALLET, to_addr="0x" + "44" * 20, value=2 * 10**18)
        engine.poll()
        event = BlockchainEvent.objects.get()
        assert event.event_type == "native_sent"
        assert event.is_large is True
        assert event.severity == "high"  # bumped from medium


class TestDeduplication:
    def test_reprocessing_same_block_creates_no_duplicates(self, chain, chain_data, wallet_monitor):
        engine = _initialized_engine(chain, chain_data, wallet_monitor)
        chain_data.add_block(101)
        chain_data.add_tx(101, from_addr="0x" + "33" * 20, to_addr=DEMO_WALLET, value=10**18)
        engine.poll()
        assert BlockchainEvent.objects.count() == 1

        # Simulate a crash before the checkpoint advanced: rewind and re-poll.
        checkpoint = BlockCheckpoint.objects.get(chain=chain)
        checkpoint.rewind_to(100)
        fresh_engine = ChainEngine(chain, client=MiniClient(chain, chain_data))
        stats = fresh_engine.poll()

        assert BlockchainEvent.objects.count() == 1  # idempotency key deduped
        assert stats["events"] == 0
        assert BlockCheckpoint.objects.get(chain=chain).last_processed_block == 101


class TestTokenEvents:
    def test_erc20_transfer_received(self, chain, chain_data, wallet_monitor):
        engine = _initialized_engine(chain, chain_data, wallet_monitor)
        chain_data.add_block(101)
        chain_data.add_log(
            101,
            address=TOKEN_ADDRESS,
            topics=[TRANSFER_TOPIC, pad_address("0x" + "55" * 20), pad_address(DEMO_WALLET)],
            data=pad_uint(1_000_000),
            log_index=3,
        )
        engine.poll()
        event = BlockchainEvent.objects.get()
        assert event.event_type == "erc20_received"
        assert event.amount_wei == Decimal(1_000_000)
        assert event.token_address.lower() == TOKEN_ADDRESS.lower()
        assert event.log_index == 3

    def test_erc721_transfer_detected_as_nft(self, chain, chain_data, wallet_monitor):
        engine = _initialized_engine(chain, chain_data, wallet_monitor)
        chain_data.add_block(101)
        chain_data.add_log(
            101,
            address=TOKEN_ADDRESS,
            topics=[
                TRANSFER_TOPIC,
                pad_address(DEMO_WALLET),
                pad_address("0x" + "66" * 20),
                pad_uint(777),  # indexed tokenId → 4 topics → ERC-721
            ],
            data="0x",
        )
        engine.poll()
        event = BlockchainEvent.objects.get()
        assert event.event_type == "nft_sent"
        assert event.token_id == "777"

    def test_approval_created_then_changed_then_revoked(self, chain, chain_data, wallet_monitor):
        engine = _initialized_engine(chain, chain_data, wallet_monitor)

        def approval_log(block, value, log_index):
            chain_data.add_block(block)
            chain_data.add_log(
                block,
                address=TOKEN_ADDRESS,
                topics=[APPROVAL_TOPIC, pad_address(DEMO_WALLET), pad_address(SPENDER)],
                data=pad_uint(value),
                log_index=log_index,
            )

        approval_log(101, 10**6, 0)
        engine.poll()
        approval_log(102, 5 * 10**6, 1)
        ChainEngine(chain._meta.model.objects.get(pk=chain.pk), client=MiniClient(chain, chain_data)).poll()
        approval_log(103, 0, 2)
        ChainEngine(chain, client=MiniClient(chain, chain_data)).poll()

        types = list(
            BlockchainEvent.objects.order_by("block_number").values_list("event_type", flat=True)
        )
        assert types == ["approval_created", "approval_changed", "approval_revoked"]

    def test_token_contract_filter(self, chain, chain_data, wallet_monitor):
        wallet_monitor.token_contract = "0x" + "99" * 20
        wallet_monitor.save()
        engine = _initialized_engine(chain, chain_data, wallet_monitor)
        chain_data.add_block(101)
        chain_data.add_log(
            101,
            address=TOKEN_ADDRESS,  # different token than the filter
            topics=[TRANSFER_TOPIC, pad_address("0x" + "55" * 20), pad_address(DEMO_WALLET)],
            data=pad_uint(1_000_000),
        )
        engine.poll()
        assert BlockchainEvent.objects.count() == 0


class TestContractSubscriptions:
    @pytest.fixture
    def contract_monitor(self, workspace, chain, user):
        from apps.monitors import abi as abi_tools
        from apps.monitors.models import ContractAbi, ContractMonitor
        from apps.monitors.services import sync_subscriptions

        abi = [
            {
                "type": "event",
                "name": "Transfer",
                "anonymous": False,
                "inputs": [
                    {"name": "from", "type": "address", "indexed": True},
                    {"name": "to", "type": "address", "indexed": True},
                    {"name": "value", "type": "uint256", "indexed": False},
                ],
            }
        ]
        doc = ContractAbi.objects.create(
            workspace=workspace, name="ERC20", abi=abi, sha256=abi_tools.abi_sha256(abi)
        )
        monitor = ContractMonitor.objects.create(
            workspace=workspace,
            chain=chain,
            name="Token watcher",
            address=TOKEN_ADDRESS,
            abi_document=doc,
            selected_events=["Transfer"],
            severity="low",
            created_by=user,
        )
        sync_subscriptions(monitor)
        return monitor

    def test_contract_event_decoded(self, chain, chain_data, contract_monitor):
        engine = ChainEngine(chain, client=MiniClient(chain, chain_data))
        engine.poll()  # initialize
        chain_data.add_block(101)
        chain_data.add_log(
            101,
            address=TOKEN_ADDRESS,
            topics=[TRANSFER_TOPIC, pad_address("0x" + "77" * 20), pad_address("0x" + "88" * 20)],
            data=pad_uint(123456),
        )
        ChainEngine(chain, client=MiniClient(chain, chain_data)).poll()

        event = BlockchainEvent.objects.get()
        assert event.event_type == "contract_event"
        assert event.contract_monitor_id == contract_monitor.pk
        assert event.decoded["event"] == "Transfer"
        assert event.decoded["params"]["value"] == 123456
        assert event.raw["address"] == TOKEN_ADDRESS

    def test_indexed_filter_excludes_non_matching(self, chain, chain_data, contract_monitor):
        contract_monitor.topic_filters = {"Transfer": {"to": "0x" + "aa" * 20}}
        contract_monitor.save()
        from apps.monitors.services import sync_subscriptions

        sync_subscriptions(contract_monitor)

        engine = ChainEngine(chain, client=MiniClient(chain, chain_data))
        engine.poll()
        chain_data.add_block(101)
        chain_data.add_log(
            101,
            address=TOKEN_ADDRESS,
            topics=[TRANSFER_TOPIC, pad_address("0x" + "77" * 20), pad_address("0x" + "88" * 20)],
            data=pad_uint(1),
        )
        ChainEngine(chain, client=MiniClient(chain, chain_data)).poll()
        assert BlockchainEvent.objects.count() == 0


class TestConfirmations:
    def test_events_confirm_at_required_depth(self, chain, chain_data, wallet_monitor, monkeypatch):
        engine = _initialized_engine(chain, chain_data, wallet_monitor)
        chain_data.add_block(101)
        chain_data.add_tx(101, from_addr="0x" + "33" * 20, to_addr=DEMO_WALLET, value=10**18)
        engine.poll()
        event = BlockchainEvent.objects.get()
        assert event.status == EventStatus.PENDING

        from apps.chains import client as client_module

        monkeypatch.setattr(
            client_module, "RpcClient", lambda chain_arg: MiniClient(chain_arg, chain_data)
        )
        from apps.events.tasks import confirm_pending_events

        # depth 1 (latest=101, block=101) — not enough for 2 confirmations
        confirm_pending_events(chain.pk)
        event.refresh_from_db()
        assert event.status == EventStatus.PENDING

        chain_data.add_block(102)  # now depth 2
        confirm_pending_events(chain.pk)
        event.refresh_from_db()
        assert event.status == EventStatus.CONFIRMED
        assert event.confirmed_at is not None

    def test_monitor_override_confirmations(self, chain, chain_data, wallet_monitor):
        wallet_monitor.confirmations_override = 5
        wallet_monitor.save()
        engine = _initialized_engine(chain, chain_data, wallet_monitor)
        chain_data.add_block(101)
        chain_data.add_tx(101, from_addr="0x" + "33" * 20, to_addr=DEMO_WALLET, value=10**18)
        engine.poll()
        assert BlockchainEvent.objects.get().confirmations_required == 5


class TestReorgHandling:
    def test_reorg_reverts_events_and_rewinds(self, chain, chain_data, wallet_monitor):
        engine = _initialized_engine(chain, chain_data, wallet_monitor)
        chain_data.add_block(101)
        chain_data.add_tx(101, from_addr="0x" + "33" * 20, to_addr=DEMO_WALLET, value=10**18)
        chain_data.add_block(102)
        engine.poll()
        assert BlockchainEvent.objects.filter(status=EventStatus.PENDING).count() == 1

        # Reorg: blocks 101-102 replaced by a different branch.
        chain_data.reorg_from(100)
        chain_data.add_block(101, hash="0x" + "f1" * 32)
        chain_data.add_block(102, hash="0x" + "f2" * 32)
        chain_data.add_block(103, hash="0x" + "f3" * 32)
        # New branch contains a DIFFERENT transaction in block 101.
        chain_data.add_tx(
            101, from_addr="0x" + "33" * 20, to_addr=DEMO_WALLET,
            value=3 * 10**18, tx_hash="0x" + "e1" * 32,
        )

        stats = ChainEngine(chain, client=MiniClient(chain, chain_data)).poll()

        assert stats["reorg"] == {"fork_block": 100, "events_reverted": 1}
        incident = ReorgIncident.objects.get()
        assert incident.fork_block == 100
        assert incident.events_reverted == 1

        reverted = BlockchainEvent.objects.filter(status=EventStatus.REVERTED)
        assert reverted.count() == 1
        assert reverted.first().reverted_at is not None

        # The replacement branch's event was ingested fresh.
        new_events = BlockchainEvent.objects.filter(status=EventStatus.PENDING)
        assert new_events.count() == 1
        assert new_events.first().amount_wei == Decimal(3 * 10**18)
        assert BlockCheckpoint.objects.get(chain=chain).last_processed_block == 103

    def test_no_reorg_when_hashes_match(self, chain, chain_data, wallet_monitor):
        engine = _initialized_engine(chain, chain_data, wallet_monitor)
        chain_data.add_block(101)
        engine.poll()
        stats = ChainEngine(chain, client=MiniClient(chain, chain_data)).poll()
        assert stats["reorg"] is None
        assert ReorgIncident.objects.count() == 0


class TestWorkspaceSuspension:
    def test_suspended_workspace_monitors_are_skipped(self, chain, chain_data, wallet_monitor):
        from django.utils import timezone

        engine = _initialized_engine(chain, chain_data, wallet_monitor)
        wallet_monitor.workspace.suspended_at = timezone.now()
        wallet_monitor.workspace.save()

        chain_data.add_block(101)
        chain_data.add_tx(101, from_addr="0x" + "33" * 20, to_addr=DEMO_WALLET, value=10**18)
        fresh = ChainEngine(chain, client=MiniClient(chain, chain_data))
        assert not fresh.has_work
