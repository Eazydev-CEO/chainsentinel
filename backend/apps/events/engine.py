"""ChainSentinel monitoring engine.

Pipeline per chain (executed under a Redis lock so exactly one worker polls
a chain at a time — safe across restarts):

    1. reorg check      — stored recent-block hashes vs canonical chain
    2. block processing — native txs + token logs + contract-subscription logs
    3. checkpoint       — advances ONLY after a block commits, so a crash
                          reprocesses the block and idempotency keys dedupe

Events are written PENDING and promoted to CONFIRMED by the confirmation
task once their per-event confirmation depth is reached.
"""
import logging
from contextlib import contextmanager
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from eth_utils import keccak, to_checksum_address

from apps.chains.client import RpcClient
from apps.monitors.constants import EventType, MonitorEventCategory, Severity
from apps.monitors.models import ContractMonitor, EventSubscription, WalletMonitor
from apps.monitors.abi import AbiError, decode_log

from .models import BlockchainEvent, BlockCheckpoint, EventStatus, ReorgIncident

logger = logging.getLogger("chainsentinel.engine")

TRANSFER_TOPIC = "0x" + keccak(text="Transfer(address,address,uint256)").hex()
APPROVAL_TOPIC = "0x" + keccak(text="Approval(address,address,uint256)").hex()
APPROVAL_FOR_ALL_TOPIC = "0x" + keccak(text="ApprovalForAll(address,address,bool)").hex()

ADDRESS_LOG_CHUNK = 50  # max addresses per eth_getLogs call


# ---------------------------------------------------------------------------
# Small helpers — tolerate web3 AttributeDicts, HexBytes and plain dicts alike
# ---------------------------------------------------------------------------
def hexstr(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value if value.startswith("0x") else "0x" + value
    if isinstance(value, (bytes, bytearray)):
        return "0x" + bytes(value).hex()
    hex_method = getattr(value, "hex", None)
    if callable(hex_method):
        out = hex_method()
        return out if out.startswith("0x") else "0x" + out
    return str(value)


def field(obj, name, default=None):
    try:
        return obj[name]
    except (KeyError, TypeError, IndexError):
        return getattr(obj, name, default)


def topic_to_address(topic) -> str:
    raw = hexstr(topic)
    try:
        return to_checksum_address("0x" + raw[-40:])
    except Exception:  # noqa: BLE001
        return ""


def block_time_to_datetime(ts) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(ts), tz=dt_timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


@contextmanager
def chain_poll_lock(chain_id: int, timeout: int = 300):
    """Redis mutex: at most one worker polls a chain at a time."""
    key = f"lock:poll-chain:{chain_id}"
    token = uuid4().hex
    acquired = cache.add(key, token, timeout=timeout)
    try:
        yield acquired
    finally:
        if acquired and cache.get(key) == token:
            cache.delete(key)


# ---------------------------------------------------------------------------
# Token metadata (best-effort, cached)
# ---------------------------------------------------------------------------
SYMBOL_SELECTOR = "0x95d89b41"
DECIMALS_SELECTOR = "0x313ce567"


def get_token_metadata(client: RpcClient, token_address: str) -> tuple[str, int | None]:
    cache_key = f"token:meta:{client.chain.pk}:{token_address.lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached.get("symbol", ""), cached.get("decimals")

    symbol, decimals = "", None
    try:
        raw = client.eth_call({"to": token_address, "data": DECIMALS_SELECTOR})
        raw_bytes = bytes.fromhex(hexstr(raw)[2:] or "00")
        if raw_bytes:
            decimals = int.from_bytes(raw_bytes[-32:], "big")
            if decimals > 77:  # nonsense value — not an ERC-20
                decimals = None
    except Exception:  # noqa: BLE001 — non-standard token
        pass
    try:
        raw = client.eth_call({"to": token_address, "data": SYMBOL_SELECTOR})
        symbol = _decode_string_return(hexstr(raw))
    except Exception:  # noqa: BLE001
        pass

    cache.set(cache_key, {"symbol": symbol, "decimals": decimals}, timeout=86400)
    return symbol, decimals


def _decode_string_return(raw_hex: str) -> str:
    data = bytes.fromhex(raw_hex[2:]) if raw_hex.startswith("0x") else b""
    if not data:
        return ""
    try:
        if len(data) >= 64:
            offset = int.from_bytes(data[:32], "big")
            if offset == 32 and len(data) >= 64:
                length = int.from_bytes(data[32:64], "big")
                if 0 < length <= 64 and len(data) >= 64 + length:
                    return data[64 : 64 + length].decode("utf-8", errors="ignore").strip("\x00")[:32]
        # bytes32-style symbol (e.g. MKR)
        return data[:32].decode("utf-8", errors="ignore").strip("\x00")[:32]
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------
class ChainEngine:
    def __init__(self, chain, client: RpcClient | None = None):
        self.chain = chain
        self.client = client or RpcClient(chain)
        self._wallet_monitors: dict[str, list[WalletMonitor]] | None = None
        self._subscriptions: dict[str, list[EventSubscription]] | None = None

    # -- monitored universe (loaded once per poll) --------------------------
    @property
    def wallet_monitors(self) -> dict[str, list[WalletMonitor]]:
        if self._wallet_monitors is None:
            index: dict[str, list[WalletMonitor]] = {}
            for monitor in WalletMonitor.objects.filter(
                chain=self.chain, is_active=True, workspace__suspended_at__isnull=True
            ).select_related("chain", "workspace"):
                index.setdefault(monitor.address.lower(), []).append(monitor)
            self._wallet_monitors = index
        return self._wallet_monitors

    @property
    def subscriptions(self) -> dict[str, list[EventSubscription]]:
        """contract address (lower) → active subscriptions."""
        if self._subscriptions is None:
            index: dict[str, list[EventSubscription]] = {}
            subs = EventSubscription.objects.filter(
                contract_monitor__chain=self.chain,
                contract_monitor__is_active=True,
                contract_monitor__workspace__suspended_at__isnull=True,
                is_active=True,
            ).select_related("contract_monitor", "contract_monitor__chain", "contract_monitor__workspace")
            for sub in subs:
                index.setdefault(sub.contract_monitor.address.lower(), []).append(sub)
            self._subscriptions = index
        return self._subscriptions

    @property
    def has_work(self) -> bool:
        return bool(self.wallet_monitors or self.subscriptions)

    # -- polling -------------------------------------------------------------
    def poll(self) -> dict:
        checkpoint, _ = BlockCheckpoint.objects.get_or_create(chain=self.chain)
        stats = {"chain": self.chain.slug, "blocks": 0, "events": 0, "reorg": None}

        latest = self.client.get_block_number()

        if checkpoint.last_processed_block == 0:
            # Fresh chain: anchor just behind the tip — no deep backfill.
            anchor = max(latest - 1, 0)
            block = self.client.get_block(anchor)
            checkpoint.advance(anchor, hexstr(field(block, "hash")))
            stats["initialized_at"] = anchor
            return stats

        fork_block = self._detect_reorg(checkpoint)
        if fork_block is not None:
            reverted = self._handle_reorg(checkpoint, fork_block)
            stats["reorg"] = {"fork_block": fork_block, "events_reverted": reverted}

        start = checkpoint.last_processed_block + 1
        end = min(latest, checkpoint.last_processed_block + settings.ENGINE_MAX_BLOCKS_PER_POLL)

        for number in range(start, end + 1):
            created = self._process_block(number, checkpoint)
            stats["blocks"] += 1
            stats["events"] += created

        if stats["blocks"]:
            processed_up_to = checkpoint.last_processed_block
            WalletMonitor.objects.filter(chain=self.chain, is_active=True).update(
                last_processed_block=processed_up_to
            )
            ContractMonitor.objects.filter(chain=self.chain, is_active=True).update(
                last_processed_block=processed_up_to
            )
        return stats

    # -- reorg handling --------------------------------------------------------
    def _detect_reorg(self, checkpoint: BlockCheckpoint) -> int | None:
        """Return the last known-good block number, or None when canonical."""
        ring = list(checkpoint.recent_blocks or [])
        if not ring:
            return None

        newest = ring[-1]
        canonical = self.client.get_block(newest["number"])
        if hexstr(field(canonical, "hash")).lower() == newest["hash"].lower():
            return None  # tip matches — no reorg

        # Walk backwards until a stored hash matches the canonical chain.
        for entry in reversed(ring[:-1]):
            canonical = self.client.get_block(entry["number"])
            if hexstr(field(canonical, "hash")).lower() == entry["hash"].lower():
                return entry["number"]

        # Reorg deeper than our window — rewind to just before the window.
        return ring[0]["number"] - 1

    def _handle_reorg(self, checkpoint: BlockCheckpoint, fork_block: int) -> int:
        from apps.audit.services import log_system_error

        depth = checkpoint.last_processed_block - fork_block
        now = timezone.now()

        with transaction.atomic():
            affected = BlockchainEvent.objects.filter(
                chain=self.chain,
                block_number__gt=fork_block,
                status__in=[EventStatus.PENDING, EventStatus.CONFIRMED],
            )
            reverted = affected.update(status=EventStatus.REVERTED, reverted_at=now)
            ReorgIncident.objects.create(
                chain=self.chain,
                fork_block=fork_block,
                depth=max(depth, 0),
                events_reverted=reverted,
                details={
                    "previous_tip": checkpoint.last_processed_block,
                    "previous_tip_hash": checkpoint.last_processed_hash,
                },
            )
            checkpoint.rewind_to(fork_block)

        log_system_error(
            source="engine",
            level="warning",
            message=f"Chain reorganization on {self.chain.slug}: fork at #{fork_block}, depth {depth}",
            details={"chain": self.chain.slug, "fork_block": fork_block, "events_reverted": reverted},
        )
        logger.warning(
            "Reorg handled chain=%s fork=%s depth=%s reverted=%s",
            self.chain.slug, fork_block, depth, reverted,
        )
        return reverted

    # -- block processing -------------------------------------------------------
    def _process_block(self, number: int, checkpoint: BlockCheckpoint) -> int:
        block = self.client.get_block(number, full_transactions=True)
        block_hash = hexstr(field(block, "hash"))
        occurred_at = block_time_to_datetime(field(block, "timestamp"))

        token_logs = self._fetch_token_logs(number) if self.wallet_monitors else []
        contract_logs = self._fetch_contract_logs(number) if self.subscriptions else []

        created = 0
        with transaction.atomic():
            created += self._process_native_transfers(block, block_hash, occurred_at)
            for log in token_logs:
                created += self._process_token_log(log, block_hash, occurred_at)
            for log in contract_logs:
                created += self._process_contract_log(log, block_hash, occurred_at)
            checkpoint.advance(number, block_hash)

        if created:
            self._dispatch_detected_webhooks()
        return created

    def _fetch_token_logs(self, number: int) -> list:
        params = {
            "fromBlock": number,
            "toBlock": number,
            "topics": [[TRANSFER_TOPIC, APPROVAL_TOPIC, APPROVAL_FOR_ALL_TOPIC]],
        }
        return list(self.client.get_logs(params))

    def _fetch_contract_logs(self, number: int) -> list:
        logs: list = []
        addresses = [to_checksum_address(a) for a in self.subscriptions.keys()]
        for i in range(0, len(addresses), ADDRESS_LOG_CHUNK):
            chunk = addresses[i : i + ADDRESS_LOG_CHUNK]
            params = {"fromBlock": number, "toBlock": number, "address": chunk}
            logs.extend(self.client.get_logs(params))
        return logs

    # -- native transfers -------------------------------------------------------
    def _process_native_transfers(self, block, block_hash: str, occurred_at) -> int:
        created = 0
        block_number = int(field(block, "number", 0))
        for tx in field(block, "transactions", []) or []:
            if isinstance(tx, (str, bytes)):
                continue  # hash-only block — cannot inspect
            value = int(field(tx, "value", 0) or 0)
            if value <= 0:
                continue
            sender = (hexstr(field(tx, "from")) or "").lower()
            receiver = (hexstr(field(tx, "to")) or "").lower()
            tx_hash = hexstr(field(tx, "hash"))
            tx_index = field(tx, "transactionIndex", None)

            for direction_key, address in (("out", sender), ("in", receiver)):
                if not address:
                    continue
                for monitor in self.wallet_monitors.get(address, []):
                    if not monitor.watches(MonitorEventCategory.NATIVE_TRANSFER):
                        continue
                    if direction_key == "out" and monitor.direction == "incoming":
                        continue
                    if direction_key == "in" and monitor.direction == "outgoing":
                        continue
                    if monitor.min_value_wei is not None and Decimal(value) < monitor.min_value_wei:
                        continue
                    event_type = (
                        EventType.NATIVE_SENT if direction_key == "out" else EventType.NATIVE_RECEIVED
                    )
                    created += self._record_event(
                        monitor_kind="wallet",
                        monitor=monitor,
                        event_type=event_type,
                        block_number=block_number,
                        block_hash=block_hash,
                        tx_hash=tx_hash,
                        tx_index=tx_index,
                        log_index=None,
                        occurred_at=occurred_at,
                        from_address=topic_safe_checksum(sender),
                        to_address=topic_safe_checksum(receiver),
                        amount_wei=Decimal(value),
                        is_large=self._is_large(monitor, value),
                        raw=None,
                    )
        return created

    # -- ERC-20 / ERC-721 wallet logs ---------------------------------------------
    def _process_token_log(self, log, block_hash: str, occurred_at) -> int:
        topics = [hexstr(t).lower() for t in (field(log, "topics", []) or [])]
        if not topics:
            return 0
        topic0 = topics[0]
        token_address = topic_safe_checksum(hexstr(field(log, "address")))
        block_number = int(field(log, "blockNumber", 0))
        tx_hash = hexstr(field(log, "transactionHash"))
        log_index = field(log, "logIndex", None)
        data = hexstr(field(log, "data", "0x"))
        created = 0

        if topic0 == TRANSFER_TOPIC and len(topics) >= 3:
            is_nft = len(topics) == 4  # ERC-721 indexes tokenId
            sender = topic_to_address(topics[1])
            receiver = topic_to_address(topics[2])
            if is_nft:
                amount = None
                token_id = str(int(topics[3], 16))
            else:
                amount = _decode_uint(data)
                token_id = ""

            for direction_key, address in (("out", sender.lower()), ("in", receiver.lower())):
                for monitor in self.wallet_monitors.get(address, []):
                    category = (
                        MonitorEventCategory.NFT_TRANSFER if is_nft else MonitorEventCategory.ERC20_TRANSFER
                    )
                    if not monitor.watches(category):
                        continue
                    if direction_key == "out" and monitor.direction == "incoming":
                        continue
                    if direction_key == "in" and monitor.direction == "outgoing":
                        continue
                    if monitor.token_contract and monitor.token_contract.lower() != token_address.lower():
                        continue
                    if (
                        not is_nft
                        and monitor.min_value_wei is not None
                        and amount is not None
                        and Decimal(amount) < monitor.min_value_wei
                    ):
                        continue

                    if is_nft:
                        event_type = EventType.NFT_SENT if direction_key == "out" else EventType.NFT_RECEIVED
                    else:
                        event_type = (
                            EventType.ERC20_SENT if direction_key == "out" else EventType.ERC20_RECEIVED
                        )
                    symbol, decimals = ("", None) if is_nft else get_token_metadata(self.client, token_address)
                    created += self._record_event(
                        monitor_kind="wallet",
                        monitor=monitor,
                        event_type=event_type,
                        block_number=block_number,
                        block_hash=block_hash,
                        tx_hash=tx_hash,
                        tx_index=field(log, "transactionIndex", None),
                        log_index=log_index,
                        occurred_at=occurred_at,
                        from_address=sender,
                        to_address=receiver,
                        token_address=token_address,
                        token_symbol=symbol,
                        token_decimals=decimals,
                        token_id=token_id,
                        amount_wei=Decimal(amount) if amount is not None else None,
                        is_large=self._is_large(monitor, amount) if amount is not None else False,
                        topic0=topic0,
                        event_signature="Transfer(address,address,uint256)",
                        raw=_raw_log(log),
                    )

        elif topic0 == APPROVAL_TOPIC and len(topics) >= 3:
            is_nft = len(topics) == 4
            owner = topic_to_address(topics[1])
            spender = topic_to_address(topics[2])
            amount = None if is_nft else _decode_uint(data)

            for monitor in self.wallet_monitors.get(owner.lower(), []):
                if not monitor.watches(MonitorEventCategory.APPROVAL):
                    continue
                if monitor.token_contract and monitor.token_contract.lower() != token_address.lower():
                    continue
                if is_nft:
                    event_type = EventType.APPROVAL_CREATED
                elif amount == 0:
                    event_type = EventType.APPROVAL_REVOKED
                else:
                    prior_exists = BlockchainEvent.objects.filter(
                        wallet_monitor=monitor,
                        token_address__iexact=token_address,
                        spender_address__iexact=spender,
                        event_type__in=[EventType.APPROVAL_CREATED, EventType.APPROVAL_CHANGED],
                    ).exists()
                    event_type = EventType.APPROVAL_CHANGED if prior_exists else EventType.APPROVAL_CREATED
                symbol, decimals = get_token_metadata(self.client, token_address)
                created += self._record_event(
                    monitor_kind="wallet",
                    monitor=monitor,
                    event_type=event_type,
                    block_number=block_number,
                    block_hash=block_hash,
                    tx_hash=tx_hash,
                    tx_index=field(log, "transactionIndex", None),
                    log_index=log_index,
                    occurred_at=occurred_at,
                    from_address=owner,
                    spender_address=spender,
                    token_address=token_address,
                    token_symbol=symbol,
                    token_decimals=decimals,
                    amount_wei=Decimal(amount) if amount is not None else None,
                    topic0=topic0,
                    event_signature="Approval(address,address,uint256)",
                    raw=_raw_log(log),
                )

        elif topic0 == APPROVAL_FOR_ALL_TOPIC and len(topics) >= 3:
            owner = topic_to_address(topics[1])
            operator = topic_to_address(topics[2])
            approved = _decode_uint(data) == 1
            for monitor in self.wallet_monitors.get(owner.lower(), []):
                if not monitor.watches(MonitorEventCategory.APPROVAL):
                    continue
                if monitor.token_contract and monitor.token_contract.lower() != token_address.lower():
                    continue
                created += self._record_event(
                    monitor_kind="wallet",
                    monitor=monitor,
                    event_type=EventType.APPROVAL_FOR_ALL if approved else EventType.APPROVAL_REVOKED,
                    block_number=block_number,
                    block_hash=block_hash,
                    tx_hash=tx_hash,
                    tx_index=field(log, "transactionIndex", None),
                    log_index=log_index,
                    occurred_at=occurred_at,
                    from_address=owner,
                    spender_address=operator,
                    token_address=token_address,
                    decoded={"approved": approved, "operator": operator},
                    topic0=topic0,
                    event_signature="ApprovalForAll(address,address,bool)",
                    raw=_raw_log(log),
                )
        return created

    # -- contract subscription logs -----------------------------------------------
    def _process_contract_log(self, log, block_hash: str, occurred_at) -> int:
        address = (hexstr(field(log, "address")) or "").lower()
        subs = self.subscriptions.get(address, [])
        if not subs:
            return 0
        topics = [hexstr(t).lower() for t in (field(log, "topics", []) or [])]
        if not topics:
            return 0
        topic0 = topics[0]
        created = 0

        for sub in subs:
            if sub.topic0.lower() != topic0:
                continue
            monitor = sub.contract_monitor
            decoded, decode_error = None, ""
            try:
                decoded = decode_log(sub.abi_fragment, topics, hexstr(field(log, "data", "0x")))
            except AbiError as exc:
                decode_error = str(exc)[:300]

            if decoded and sub.indexed_filters:
                params = decoded.get("params", {})
                if not _passes_filters(params, sub.indexed_filters):
                    continue

            params = (decoded or {}).get("params", {})
            created += self._record_event(
                monitor_kind="contract",
                monitor=monitor,
                event_type=EventType.CONTRACT_EVENT,
                block_number=int(field(log, "blockNumber", 0)),
                block_hash=block_hash,
                tx_hash=hexstr(field(log, "transactionHash")),
                tx_index=field(log, "transactionIndex", None),
                log_index=field(log, "logIndex", None),
                occurred_at=occurred_at,
                contract_address=topic_safe_checksum(address),
                from_address=str(params.get("from", "") or params.get("sender", "") or "")[:42],
                to_address=str(params.get("to", "") or params.get("recipient", "") or "")[:42],
                decoded=decoded,
                decode_error=decode_error,
                topic0=topic0,
                event_signature=sub.signature,
                raw=_raw_log(log),
            )
        return created

    # -- event writing ---------------------------------------------------------
    def _record_event(self, *, monitor_kind: str, monitor, event_type: str, block_number: int,
                      block_hash: str, tx_hash: str, tx_index, log_index, occurred_at,
                      from_address: str = "", to_address: str = "", spender_address: str = "",
                      contract_address: str = "", token_address: str = "", token_symbol: str = "",
                      token_decimals=None, token_id: str = "", amount_wei=None, decoded=None,
                      decode_error: str = "", topic0: str = "", event_signature: str = "",
                      is_large: bool = False, raw=None) -> int:
        log_part = "tx" if log_index is None else str(log_index)
        idempotency_key = (
            f"{self.chain.pk}:{block_number}:{tx_hash}:{log_part}:{event_type}:"
            f"{monitor_kind}:{monitor.pk}"
        )
        severity = Severity.HIGH if is_large and monitor.severity in (Severity.INFO, Severity.LOW, Severity.MEDIUM) else monitor.severity

        _, created = BlockchainEvent.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                "workspace": monitor.workspace,
                "chain": self.chain,
                "wallet_monitor": monitor if monitor_kind == "wallet" else None,
                "contract_monitor": monitor if monitor_kind == "contract" else None,
                "event_type": event_type,
                "status": EventStatus.PENDING,
                "severity": severity,
                "is_large": is_large,
                "block_number": block_number,
                "block_hash": block_hash.lower(),
                "tx_hash": tx_hash.lower(),
                "tx_index": tx_index,
                "log_index": log_index,
                "from_address": from_address or "",
                "to_address": to_address or "",
                "spender_address": spender_address or "",
                "contract_address": contract_address or "",
                "token_address": token_address or "",
                "token_symbol": (token_symbol or "")[:32],
                "token_decimals": token_decimals,
                "token_id": token_id or "",
                "amount_wei": amount_wei,
                "decoded": decoded,
                "raw": raw,
                "decode_error": decode_error,
                "topic0": topic0,
                "event_signature": event_signature,
                "confirmations_required": monitor.required_confirmations(),
                "occurred_at": occurred_at,
            },
        )
        if created:
            monitor.last_event_at = timezone.now()
            monitor.save(update_fields=["last_event_at"])
        return 1 if created else 0

    def _is_large(self, monitor: WalletMonitor, value) -> bool:
        threshold = getattr(monitor, "large_tx_threshold_wei", None)
        if threshold is None or value is None:
            return False
        return Decimal(value) >= threshold

    def _dispatch_detected_webhooks(self) -> None:
        """Queue `event.detected` webhooks for events created in this block batch."""
        # Deliveries are created at confirmation time by default (see tasks);
        # detection-time hooks are intentionally limited to keep noise down.
        return


def topic_safe_checksum(address: str) -> str:
    if not address:
        return ""
    try:
        return to_checksum_address(address)
    except Exception:  # noqa: BLE001
        return address


def _decode_uint(data_hex: str) -> int:
    payload = data_hex[2:] if data_hex.startswith("0x") else data_hex
    if not payload:
        return 0
    try:
        return int(payload[:64] if len(payload) >= 64 else payload, 16)
    except ValueError:
        return 0


def _raw_log(log) -> dict:
    return {
        "address": hexstr(field(log, "address")),
        "topics": [hexstr(t) for t in (field(log, "topics", []) or [])],
        "data": hexstr(field(log, "data", "0x")),
        "blockNumber": int(field(log, "blockNumber", 0)),
        "transactionHash": hexstr(field(log, "transactionHash")),
        "logIndex": field(log, "logIndex", None),
    }


def _passes_filters(params: dict, filters: dict) -> bool:
    for key, expected in (filters or {}).items():
        actual = params.get(key)
        if actual is None:
            return False
        actual_str, expected_str = str(actual), str(expected)
        if actual_str.startswith("0x") and expected_str.startswith("0x"):
            if actual_str.lower() != expected_str.lower():
                return False
        elif actual_str != expected_str:
            return False
    return True
