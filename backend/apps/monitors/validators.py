"""EVM address validation & normalization (EIP-55 checksum)."""
from eth_utils import is_address, is_checksum_address, to_checksum_address
from rest_framework import serializers


def normalize_evm_address(value: str) -> str:
    """Return the EIP-55 checksummed form of an EVM address.

    Raises `serializers.ValidationError` for anything that is not a valid
    20-byte hex address. Mixed-case inputs must be valid checksums already
    (catches typos); all-lower/all-upper inputs are normalized.
    """
    if not isinstance(value, str):
        raise serializers.ValidationError("Address must be a string.")
    candidate = value.strip()
    if not candidate.startswith("0x") and not candidate.startswith("0X"):
        raise serializers.ValidationError("Address must start with 0x.")
    if len(candidate) != 42:
        raise serializers.ValidationError("Address must be 42 characters (0x + 40 hex).")
    if not is_address(candidate):
        raise serializers.ValidationError("Not a valid EVM address.")

    hex_part = candidate[2:]
    is_mixed_case = hex_part != hex_part.lower() and hex_part != hex_part.upper()
    if is_mixed_case and not is_checksum_address(candidate):
        raise serializers.ValidationError(
            "Address checksum is invalid — double-check for typos."
        )
    return to_checksum_address(candidate)


def addresses_equal(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return a.lower() == b.lower()
