"""ABI parsing, event signature/topic generation, log decoding."""
import json

import pytest

from apps.monitors.abi import (
    AbiError,
    abi_sha256,
    decode_log,
    event_signature,
    event_topic0,
    extract_events,
    parse_abi,
)

TRANSFER_EVENT = {
    "type": "event",
    "name": "Transfer",
    "anonymous": False,
    "inputs": [
        {"name": "from", "type": "address", "indexed": True},
        {"name": "to", "type": "address", "indexed": True},
        {"name": "value", "type": "uint256", "indexed": False},
    ],
}

ERC20_ABI = [
    TRANSFER_EVENT,
    {"type": "function", "name": "transfer", "inputs": [], "outputs": []},
]


class TestParseAbi:
    def test_parses_json_string(self):
        parsed = parse_abi(json.dumps(ERC20_ABI))
        assert len(parsed) == 2

    def test_accepts_wrapped_abi_object(self):
        parsed = parse_abi(json.dumps({"abi": ERC20_ABI}))
        assert parsed[0]["name"] == "Transfer"

    def test_rejects_invalid_json(self):
        with pytest.raises(AbiError, match="not valid JSON"):
            parse_abi("{not json")

    def test_rejects_non_array(self):
        with pytest.raises(AbiError, match="array"):
            parse_abi('{"type": "event"}')

    def test_rejects_empty(self):
        with pytest.raises(AbiError, match="empty"):
            parse_abi("[]")

    def test_rejects_oversized(self, settings):
        settings.ABI_MAX_BYTES = 100
        with pytest.raises(AbiError, match="too large"):
            parse_abi(json.dumps(ERC20_ABI * 50))

    def test_rejects_event_without_name(self):
        with pytest.raises(AbiError, match="missing a name"):
            parse_abi(json.dumps([{"type": "event", "inputs": []}]))

    def test_rejects_malformed_inputs(self):
        bad = [{"type": "event", "name": "X", "inputs": [{"type": 5}]}]
        with pytest.raises(AbiError, match="malformed"):
            parse_abi(json.dumps(bad))

    def test_never_crashes_on_garbage(self):
        for garbage in ["null", "42", '"str"', '[{"type": []}]', '[[]]']:
            with pytest.raises(AbiError):
                parse_abi(garbage)


class TestSignatures:
    def test_transfer_signature(self):
        assert event_signature(TRANSFER_EVENT) == "Transfer(address,address,uint256)"

    def test_transfer_topic0_matches_known_hash(self):
        assert (
            event_topic0(TRANSFER_EVENT)
            == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
        )

    def test_tuple_types_are_canonicalized(self):
        event = {
            "type": "event",
            "name": "OrderFilled",
            "inputs": [
                {
                    "name": "order",
                    "type": "tuple",
                    "indexed": False,
                    "components": [
                        {"name": "maker", "type": "address"},
                        {"name": "amount", "type": "uint256"},
                    ],
                }
            ],
        }
        assert event_signature(event) == "OrderFilled((address,uint256))"

    def test_extract_events_lists_only_events(self):
        events = extract_events(ERC20_ABI)
        assert len(events) == 1
        assert events[0]["name"] == "Transfer"
        assert events[0]["topic0"].startswith("0x")
        assert [i["indexed"] for i in events[0]["inputs"]] == [True, True, False]

    def test_sha256_is_stable_across_key_order(self):
        a = [{"type": "event", "name": "E", "inputs": []}]
        b = [{"inputs": [], "name": "E", "type": "event"}]
        assert abi_sha256(a) == abi_sha256(b)


class TestDecodeLog:
    FROM = "0x" + "11" * 20
    TO = "0x" + "22" * 20

    def _topics(self):
        return [
            event_topic0(TRANSFER_EVENT),
            "0x" + self.FROM[2:].rjust(64, "0"),
            "0x" + self.TO[2:].rjust(64, "0"),
        ]

    def test_decodes_transfer(self):
        value = 1_500_000_000_000_000_000_000  # > 2^53 → serialized as string
        data = "0x" + format(value, "064x")
        decoded = decode_log(TRANSFER_EVENT, self._topics(), data)
        assert decoded["event"] == "Transfer"
        assert decoded["params"]["from"].lower() == self.FROM
        assert decoded["params"]["to"].lower() == self.TO
        assert decoded["params"]["value"] == str(value)

    def test_small_ints_stay_numeric(self):
        data = "0x" + format(42, "064x")
        decoded = decode_log(TRANSFER_EVENT, self._topics(), data)
        assert decoded["params"]["value"] == 42

    def test_topic_count_mismatch_raises(self):
        with pytest.raises(AbiError, match="Indexed parameter count"):
            decode_log(TRANSFER_EVENT, self._topics()[:2], "0x" + "0" * 64)

    def test_bad_data_raises(self):
        with pytest.raises(AbiError, match="Failed to decode data"):
            decode_log(TRANSFER_EVENT, self._topics(), "0x1234")

    def test_indexed_dynamic_type_reported_as_hash(self):
        event = {
            "type": "event",
            "name": "Named",
            "inputs": [{"name": "label", "type": "string", "indexed": True}],
        }
        digest = "0x" + "ab" * 32
        decoded = decode_log(event, [event_topic0(event), digest], "0x")
        assert decoded["params"]["label"] == {"hashed": digest}
