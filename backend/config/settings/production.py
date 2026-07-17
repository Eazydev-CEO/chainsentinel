"""Production settings — hardened. Requires real env configuration."""
from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE, PLATFORM_ALERT_EMAILS, SECRET_KEY
from .env import env_bool, env_str

DEBUG = False

if SECRET_KEY == "dev-only-insecure-secret-key-change-me":  # pragma: no cover
    raise RuntimeError("DJANGO_SECRET_KEY must be set in production.")

# Fail fast on a missing/broken webhook encryption key instead of at first use.
from .base import WEBHOOK_ENCRYPTION_KEY  # noqa: E402

if not WEBHOOK_ENCRYPTION_KEY:  # pragma: no cover
    raise RuntimeError(
        "WEBHOOK_ENCRYPTION_KEY must be set in production "
        "(python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\")."
    )
try:  # pragma: no cover
    from cryptography.fernet import Fernet as _Fernet

    _Fernet(WEBHOOK_ENCRYPTION_KEY.encode())
except ValueError as _exc:  # pragma: no cover
    raise RuntimeError("WEBHOOK_ENCRYPTION_KEY is not a valid Fernet key.") from _exc

# Static files served by WhiteNoise behind nginx (admin/swagger assets).
MIDDLEWARE = MIDDLEWARE[:1] + ["whitenoise.middleware.WhiteNoiseMiddleware"] + MIDDLEWARE[1:]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Cookies / transport security
SECURE_COOKIES = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)  # nginx usually handles this
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

# Production error emails to platform operators (if configured)
ADMINS = [("ChainSentinel Ops", email) for email in PLATFORM_ALERT_EMAILS]
SERVER_EMAIL = env_str("DEFAULT_FROM_EMAIL", "ChainSentinel <no-reply@localhost>")
