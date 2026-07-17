"""Webhook secret encryption at rest (Fernet)."""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet() -> Fernet:
    key = settings.WEBHOOK_ENCRYPTION_KEY
    if not key:
        # Development fallback: deterministic key derived from SECRET_KEY.
        # Production must set WEBHOOK_ENCRYPTION_KEY explicitly (see .env.example).
        digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except ValueError as exc:
        raise ValueError(
            "WEBHOOK_ENCRYPTION_KEY is not a valid Fernet key. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())" — or leave it empty in development.'
        ) from exc


def encrypt_secret(raw: str) -> str:
    return _fernet().encrypt(raw.encode()).decode()


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError(
            "Webhook secret cannot be decrypted — WEBHOOK_ENCRYPTION_KEY changed?"
        ) from exc
