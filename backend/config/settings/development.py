"""Development settings — relaxed security, console email fallback."""
from .base import *  # noqa: F401,F403
from .base import EMAIL_HOST
from .env import env_bool

DEBUG = env_bool("DJANGO_DEBUG", True)

# Console email when no SMTP host is configured locally.
if not EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Local dev may run without Redis (e.g. plain runserver + sqlite-free flows).
# Keep Redis default; individual devs can override via env.
