"""Test settings — SQLite, eager Celery, in-memory cache/email. No network."""
from .base import *  # noqa: F401,F403
from .base import BASE_DIR, REST_FRAMEWORK

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_db.sqlite3",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "chainsentinel-tests",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # speed only

WEBHOOK_ENCRYPTION_KEY = "5Fj9tqzOMOJ1V0dgIU2B0kOsCkFsC0DPLnbQ4uJ4Zx0="  # test-only Fernet key

# Generous throttle rates so unrelated tests never trip scoped throttles;
# throttling behaviour itself is covered by dedicated tests with overrides.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_CLASSES": (),
    "DEFAULT_THROTTLE_RATES": {
        key: "10000/min" for key in REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    },
}
