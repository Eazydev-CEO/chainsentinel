"""HMAC SHA-256 webhook signing (Stripe-style `t=<ts>,v1=<sig>` scheme).

Receivers verify with:

    signed = f"{timestamp}.{raw_body}"
    expected = hmac.new(secret, signed.encode(), hashlib.sha256).hexdigest()
    hmac.compare_digest(expected, received_v1)

Reject if |now - timestamp| exceeds your tolerance (we recommend 5 minutes).
"""
import hashlib
import hmac


def sign_payload(secret: str, timestamp: int | str, body: str) -> str:
    message = f"{timestamp}.{body}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def signature_header(secret: str, timestamp: int | str, body: str) -> str:
    return f"t={timestamp},v1={sign_payload(secret, timestamp, body)}"


def verify_signature(secret: str, timestamp: int | str, body: str, signature: str) -> bool:
    expected = sign_payload(secret, timestamp, body)
    return hmac.compare_digest(expected, signature)
