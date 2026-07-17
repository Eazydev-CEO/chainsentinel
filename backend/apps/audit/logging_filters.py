import logging

from .redaction import SENSITIVE_PATTERNS


class RedactSecretsFilter(logging.Filter):
    """Scrub API keys / JWTs / secrets from every log line."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
            redacted = message
            for pattern in SENSITIVE_PATTERNS:
                redacted = pattern.sub("[REDACTED]", redacted)
            if redacted != message:
                record.msg = redacted
                record.args = ()
        except Exception:  # pragma: no cover — logging must never raise
            pass
        return True
