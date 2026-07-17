"""Shared monitoring domain constants (upstream of events/alerts/webhooks)."""
from django.db import models


class Severity(models.TextChoices):
    INFO = "info", "Info"
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"


SEVERITY_ORDER: dict[str, int] = {
    Severity.INFO: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


class Direction(models.TextChoices):
    INCOMING = "incoming", "Incoming"
    OUTGOING = "outgoing", "Outgoing"
    BOTH = "both", "Both"


class MonitorEventCategory(models.TextChoices):
    """What a wallet monitor subscribes to."""

    NATIVE_TRANSFER = "native_transfer", "Native token transfers"
    ERC20_TRANSFER = "erc20_transfer", "ERC-20 transfers"
    NFT_TRANSFER = "nft_transfer", "NFT transfers (ERC-721)"
    APPROVAL = "approval", "Token approvals & revocations"


class EventType(models.TextChoices):
    """Concrete event types stored on BlockchainEvent rows."""

    NATIVE_RECEIVED = "native_received", "Native received"
    NATIVE_SENT = "native_sent", "Native sent"
    ERC20_RECEIVED = "erc20_received", "ERC-20 received"
    ERC20_SENT = "erc20_sent", "ERC-20 sent"
    NFT_RECEIVED = "nft_received", "NFT received"
    NFT_SENT = "nft_sent", "NFT sent"
    APPROVAL_CREATED = "approval_created", "Approval created"
    APPROVAL_CHANGED = "approval_changed", "Approval changed"
    APPROVAL_REVOKED = "approval_revoked", "Approval revoked"
    APPROVAL_FOR_ALL = "approval_for_all", "Approval for all (operator)"
    CONTRACT_EVENT = "contract_event", "Contract event"


# Virtual type usable in alert rules: matches any event flagged is_large.
LARGE_TRANSFER = "large_transfer"

ALERTABLE_EVENT_TYPES: list[tuple[str, str]] = list(EventType.choices) + [
    (LARGE_TRANSFER, "Large transfer (threshold)")
]
