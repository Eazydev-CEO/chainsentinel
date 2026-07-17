"""Safe ABI parsing, event-signature generation, and log decoding.

Malformed ABIs must never crash the platform: every entry point either
returns a clean result or raises `AbiError` with a human-readable message.
"""
import hashlib
import json
from typing import Any

from django.conf import settings
from eth_abi import decode as abi_decode
from eth_utils import keccak, to_checksum_address


class AbiError(Exception):
    """Raised for any invalid / oversized / undecodable ABI input."""


# --------------------------------------------------------------------------
# Parsing & validation
# --------------------------------------------------------------------------
def parse_abi(raw: str | bytes | list) -> list[dict]:
    """Parse and validate an ABI JSON document. Returns the ABI list."""
    if isinstance(raw, (str, bytes)):
        if len(raw) > settings.ABI_MAX_BYTES:
            raise AbiError(
                f"ABI is too large (max {settings.ABI_MAX_BYTES // 1024} KB)."
            )
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AbiError(f"ABI is not valid JSON: {exc.msg} (line {exc.lineno}).") from exc
    else:
        parsed = raw

    # Some tooling exports {"abi": [...]} wrappers — accept them.
    if isinstance(parsed, dict) and isinstance(parsed.get("abi"), list):
        parsed = parsed["abi"]

    if not isinstance(parsed, list):
        raise AbiError("ABI must be a JSON array of entries.")
    if not parsed:
        raise AbiError("ABI is empty.")

    for i, entry in enumerate(parsed):
        if not isinstance(entry, dict):
            raise AbiError(f"ABI entry #{i} is not an object.")
        entry_type = entry.get("type", "function")
        if not isinstance(entry_type, str):
            raise AbiError(f"ABI entry #{i} has a non-string type.")
        if entry_type == "event":
            _validate_event_entry(entry, i)
    return parsed


def _validate_event_entry(entry: dict, index: int) -> None:
    name = entry.get("name")
    if not name or not isinstance(name, str):
        raise AbiError(f"ABI event entry #{index} is missing a name.")
    inputs = entry.get("inputs", [])
    if not isinstance(inputs, list):
        raise AbiError(f"ABI event '{name}' has invalid inputs.")
    for j, inp in enumerate(inputs):
        if not isinstance(inp, dict) or not isinstance(inp.get("type"), str):
            raise AbiError(f"ABI event '{name}' input #{j} is malformed.")


def abi_sha256(abi: list) -> str:
    canonical = json.dumps(abi, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


# --------------------------------------------------------------------------
# Event signatures & topics
# --------------------------------------------------------------------------
def canonical_type(inp: dict) -> str:
    """Canonical ABI type, expanding tuples recursively."""
    typ = inp.get("type", "")
    if typ.startswith("tuple"):
        components = inp.get("components", [])
        inner = ",".join(canonical_type(c) for c in components)
        suffix = typ[len("tuple"):]  # e.g. "", "[]", "[2]"
        return f"({inner}){suffix}"
    return typ


def event_signature(event_abi: dict) -> str:
    """e.g. Transfer(address,address,uint256)"""
    name = event_abi.get("name", "")
    types = ",".join(canonical_type(i) for i in event_abi.get("inputs", []))
    return f"{name}({types})"


def event_topic0(event_abi: dict) -> str:
    return "0x" + keccak(text=event_signature(event_abi)).hex()


def extract_events(abi: list) -> list[dict]:
    """List the events an ABI defines, with signatures and topic hashes."""
    events = []
    for entry in abi:
        if entry.get("type") != "event":
            continue
        signature = event_signature(entry)
        events.append(
            {
                "name": entry.get("name"),
                "signature": signature,
                "topic0": event_topic0(entry),
                "anonymous": bool(entry.get("anonymous", False)),
                "inputs": [
                    {
                        "name": i.get("name", ""),
                        "type": canonical_type(i),
                        "indexed": bool(i.get("indexed", False)),
                    }
                    for i in entry.get("inputs", [])
                ],
            }
        )
    return events


# --------------------------------------------------------------------------
# Log decoding
# --------------------------------------------------------------------------
_DYNAMIC_TYPES = ("string", "bytes")


def _is_dynamic(typ: str) -> bool:
    return typ in _DYNAMIC_TYPES or typ.endswith("]") or typ.startswith("(")


def _json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if isinstance(value, int):
        # uint256 values overflow JS numbers — ship big ints as strings.
        return str(value) if abs(value) > 2**53 - 1 else value
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _checksum_if_address(typ: str, value: Any) -> Any:
    if typ == "address" and isinstance(value, str):
        try:
            return to_checksum_address(value)
        except Exception:  # noqa: BLE001
            return value
    return value


def decode_log(event_abi: dict, topics: list[str | bytes], data: str | bytes) -> dict:
    """Decode a raw log against one ABI event definition.

    Returns {"event", "signature", "params": {name: value}}.
    Raises AbiError when the log does not match the ABI.
    """
    def to_bytes(item: str | bytes) -> bytes:
        if isinstance(item, bytes):
            return item
        return bytes.fromhex(item[2:] if item.startswith("0x") else item)

    inputs = event_abi.get("inputs", [])
    indexed = [i for i in inputs if i.get("indexed")]
    unindexed = [i for i in inputs if not i.get("indexed")]

    topic_items = list(topics)
    if not event_abi.get("anonymous", False):
        if not topic_items:
            raise AbiError("Log has no topics.")
        topic_items = topic_items[1:]  # drop topic0 (the signature hash)

    if len(topic_items) != len(indexed):
        raise AbiError(
            f"Indexed parameter count mismatch for {event_abi.get('name')}: "
            f"log has {len(topic_items)}, ABI expects {len(indexed)}."
        )

    params: dict[str, Any] = {}

    for inp, topic in zip(indexed, topic_items):
        typ = canonical_type(inp)
        name = inp.get("name") or f"param{len(params)}"
        raw = to_bytes(topic)
        if _is_dynamic(typ):
            # Indexed dynamic values are stored as their keccak hash on-chain.
            params[name] = {"hashed": "0x" + raw.hex()}
        else:
            try:
                value = abi_decode([typ], raw)[0]
            except Exception as exc:  # noqa: BLE001
                raise AbiError(f"Failed to decode indexed '{name}' as {typ}.") from exc
            params[name] = _json_safe(_checksum_if_address(typ, value))

    if unindexed:
        types = [canonical_type(i) for i in unindexed]
        try:
            values = abi_decode(types, to_bytes(data) if data else b"")
        except Exception as exc:  # noqa: BLE001
            raise AbiError(
                f"Failed to decode data for {event_abi.get('name')} as ({', '.join(types)})."
            ) from exc
        for inp, value in zip(unindexed, values):
            name = inp.get("name") or f"param{len(params)}"
            params[name] = _json_safe(_checksum_if_address(canonical_type(inp), value))

    return {
        "event": event_abi.get("name"),
        "signature": event_signature(event_abi),
        "params": params,
    }
