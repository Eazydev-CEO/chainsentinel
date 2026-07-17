"""Sensitive-value redaction for logs, audit metadata, and stored errors."""
import re

SENSITIVE_KEYS = {
    "password",
    "current_password",
    "new_password",
    "secret",
    "token",
    "refresh",
    "access",
    "authorization",
    "api_key",
    "x-api-key",
    "hashed_key",
    "signature",
    "smtp_password",
    "cookie",
}

SENSITIVE_PATTERNS = [
    re.compile(r"cs_[a-f0-9]{8}_[A-Za-z0-9_\-]{20,}"),  # API keys
    re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),  # JWTs
    re.compile(r"whsec_[A-Za-z0-9_\-]{10,}"),  # webhook secrets
    re.compile(r"(?i)(password|secret|token)=[^&\s]+"),
]


def redact_sensitive(value):
    """Recursively redact dict/list structures by key name and value shape."""
    if isinstance(value, dict):
        return {
            k: ("[REDACTED]" if str(k).lower() in SENSITIVE_KEYS else redact_sensitive(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str):
        for pattern in SENSITIVE_PATTERNS:
            value = pattern.sub("[REDACTED]", value)
        return value
    return value
