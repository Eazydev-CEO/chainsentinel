"""Mocked Web3 / RPC layers — tests never touch a real network."""
from decimal import Decimal


class FakeChainData:
    """In-memory canonical chain the fakes serve."""

    def __init__(self):
        self.blocks: dict[int, dict] = {}
        self.logs: dict[int, list[dict]] = {}
        self.latest = 0
        self.eth_call_results: dict[str, str] = {}  # data-selector → return hex

    def add_block(self, number: int, *, hash: str | None = None, txs: list | None = None,
                  timestamp: int = 1_700_000_000):
        self.blocks[number] = {
            "number": number,
            "hash": hash or f"0x{number:064x}",
            "parentHash": self.blocks.get(number - 1, {}).get("hash", f"0x{number - 1:064x}"),
            "timestamp": timestamp + number,
            "transactions": txs or [],
        }
        self.latest = max(self.latest, number)
        return self.blocks[number]

    def add_tx(self, block_number: int, *, from_addr: str, to_addr: str | None, value: int,
               tx_hash: str | None = None, index: int = 0) -> dict:
        tx = {
            "hash": tx_hash or f"0x{'t' * 40}{block_number:04x}{index:02x}".replace("t", "a"),
            "from": from_addr,
            "to": to_addr,
            "value": value,
            "transactionIndex": index,
        }
        self.blocks[block_number]["transactions"].append(tx)
        return tx

    def add_log(self, block_number: int, *, address: str, topics: list[str], data: str = "0x",
                tx_hash: str | None = None, log_index: int = 0) -> dict:
        log = {
            "address": address,
            "topics": topics,
            "data": data,
            "blockNumber": block_number,
            "transactionHash": tx_hash or f"0x{'b' * 60}{block_number:02x}{log_index:02x}",
            "transactionIndex": 0,
            "logIndex": log_index,
        }
        self.logs.setdefault(block_number, []).append(log)
        return log

    def reorg_from(self, fork_block: int):
        """Drop all blocks above fork_block (they'll be re-added with new hashes)."""
        for number in [n for n in self.blocks if n > fork_block]:
            del self.blocks[number]
            self.logs.pop(number, None)
        self.latest = fork_block


class FakeEth:
    def __init__(self, data: FakeChainData):
        self._data = data
        self.calls: list[tuple] = []

    @property
    def block_number(self) -> int:
        self.calls.append(("block_number",))
        return self._data.latest

    @property
    def chain_id(self) -> int:
        return 31337

    def get_block(self, identifier, full_transactions: bool = False):
        self.calls.append(("get_block", identifier, full_transactions))
        block = self._data.blocks.get(identifier)
        if block is None:
            raise ValueError(f"Block {identifier} not found")
        if full_transactions:
            return block
        return {**block, "transactions": [t["hash"] for t in block["transactions"]]}

    def get_logs(self, params: dict):
        self.calls.append(("get_logs", params))
        start = params.get("fromBlock", 0)
        end = params.get("toBlock", self._data.latest)
        wanted_addresses = params.get("address")
        if isinstance(wanted_addresses, str):
            wanted_addresses = [wanted_addresses]
        wanted_topic0 = None
        topics = params.get("topics")
        if topics and topics[0]:
            first = topics[0]
            wanted_topic0 = {t.lower() for t in (first if isinstance(first, list) else [first])}

        results = []
        for number in range(start, end + 1):
            for log in self._data.logs.get(number, []):
                if wanted_addresses is not None and log["address"].lower() not in {
                    a.lower() for a in wanted_addresses
                }:
                    continue
                if wanted_topic0 is not None and log["topics"][0].lower() not in wanted_topic0:
                    continue
                results.append(log)
        return results

    def call(self, tx: dict):
        self.calls.append(("eth_call", tx))
        selector = (tx.get("data") or "")[:10]
        result = self._data.eth_call_results.get(selector)
        if result is None:
            raise ValueError("execution reverted")
        return bytes.fromhex(result[2:] if result.startswith("0x") else result)


class FakeWeb3:
    def __init__(self, data: FakeChainData):
        self.eth = FakeEth(data)


class FailingWeb3:
    """Every access raises the configured exception (failover tests)."""

    class _Eth:
        def __init__(self, exc: Exception):
            self._exc = exc
            self.attempts = 0

        @property
        def block_number(self):
            self.attempts += 1
            raise self._exc

        def get_block(self, *a, **k):
            self.attempts += 1
            raise self._exc

        def get_logs(self, *a, **k):
            self.attempts += 1
            raise self._exc

        def call(self, *a, **k):
            self.attempts += 1
            raise self._exc

    def __init__(self, exc: Exception):
        self.eth = self._Eth(exc)


class MiniClient:
    """Drop-in for RpcClient in engine tests — no providers, no failover."""

    def __init__(self, chain, data: FakeChainData):
        self.chain = chain
        self._eth = FakeEth(data)

    def get_block_number(self) -> int:
        return self._eth.block_number

    def get_block(self, identifier, full_transactions: bool = False):
        return self._eth.get_block(identifier, full_transactions=full_transactions)

    def get_logs(self, params: dict):
        return self._eth.get_logs(params)

    def eth_call(self, tx: dict):
        return self._eth.call(tx)


# Convenient constants for building token logs.
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
APPROVAL_TOPIC = "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925"
APPROVAL_FOR_ALL_TOPIC = "0x17307eab39ab6107e8899845ad3d59bd9653f200f220920489ca2b5937696c31"


def pad_address(address: str) -> str:
    return "0x" + address[2:].lower().rjust(64, "0")


def pad_uint(value: int) -> str:
    return "0x" + format(value, "064x")
