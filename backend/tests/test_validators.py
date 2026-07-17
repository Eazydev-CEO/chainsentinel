"""EVM address validation & EIP-55 normalization."""
import pytest
from rest_framework import serializers

from apps.monitors.validators import addresses_equal, normalize_evm_address

CHECKSUMMED = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"


def test_lowercase_address_is_checksummed():
    assert normalize_evm_address(CHECKSUMMED.lower()) == CHECKSUMMED


def test_uppercase_hex_is_checksummed():
    assert normalize_evm_address("0x" + CHECKSUMMED[2:].upper()) == CHECKSUMMED


def test_valid_checksum_passes_through():
    assert normalize_evm_address(CHECKSUMMED) == CHECKSUMMED


def test_surrounding_whitespace_is_stripped():
    assert normalize_evm_address(f"  {CHECKSUMMED}  ") == CHECKSUMMED


@pytest.mark.parametrize(
    "bad",
    [
        "d8dA6BF26964aF9D7eEd9e03E53415D37aA96045",  # missing 0x
        "0x1234",  # too short
        "0x" + "g" * 40,  # non-hex
        "0x" + "1" * 41,  # wrong length
        "",
        "not-an-address",
    ],
)
def test_invalid_addresses_rejected(bad):
    with pytest.raises(serializers.ValidationError):
        normalize_evm_address(bad)


def test_bad_mixed_case_checksum_rejected():
    # Flip the case of one character in an otherwise valid checksum.
    tampered = CHECKSUMMED[:-1] + ("5" if CHECKSUMMED[-1] != "5" else "6")
    corrupted = "0xD8dA6BF26964aF9D7eEd9e03E53415D37aA96045"  # first char case flipped
    with pytest.raises(serializers.ValidationError):
        normalize_evm_address(corrupted)


def test_non_string_rejected():
    with pytest.raises(serializers.ValidationError):
        normalize_evm_address(12345)


def test_addresses_equal_is_case_insensitive():
    assert addresses_equal(CHECKSUMMED, CHECKSUMMED.lower())
    assert not addresses_equal(CHECKSUMMED, None)
    assert not addresses_equal(None, None)
