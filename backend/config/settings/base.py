"""
ChainSentinel — base Django settings.

Everything secret or environment-specific comes from environment variables.
See .env.example at the repository root and docs/ENVIRONMENT.md.
"""
from datetime import timedelta
from pathlib import Path

from .env import env_bool, env_csv, env_int, env_str

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
REPO_ROOT = BASE_DIR.parent

SECRET_KEY = env_str("DJANGO_SECRET_KEY", "dev-only-insecure-secret-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_csv("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])

FRONTEND_URL = env_str("FRONTEND_URL", "http://localhost:3026").rstrip("/")
BACKEND_URL = env_str("BACKEND_URL", "http://localhost:8212").rstrip("/")

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    # ChainSentinel apps
    "apps.accounts",
    "apps.workspaces",
    "apps.chains",
    "apps.monitors",
    "apps.events",
    "apps.alerts",
    "apps.webhooks",
    "apps.notifications",
    "apps.audit",
    "apps.api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.api.middleware.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database — PostgreSQL is the only supported production database
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env_str("POSTGRES_DB", "chainsentinel"),
        "USER": env_str("POSTGRES_USER", "chainsentinel"),
        "PASSWORD": env_str("POSTGRES_PASSWORD", ""),
        "HOST": env_str("POSTGRES_HOST", "localhost"),
        "PORT": env_str("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Cookie names used by the SPA auth flow
JWT_ACCESS_COOKIE = "cs_access"
JWT_REFRESH_COOKIE = "cs_refresh"
JWT_SESSION_MARKER_COOKIE = "cs_session"
SECURE_COOKIES = env_bool("SECURE_COOKIES", False)

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env_int("JWT_ACCESS_MINUTES", 15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env_int("JWT_REFRESH_DAYS", 14)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Email verification / password reset token lifetimes (seconds)
EMAIL_VERIFICATION_MAX_AGE = 60 * 60 * 48  # 48 hours
PASSWORD_RESET_MAX_AGE = 60 * 60 * 2  # 2 hours
INVITATION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days

# ---------------------------------------------------------------------------
# DRF
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.CookieJWTAuthentication",
        "apps.accounts.authentication.ApiKeyAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "apps.api.pagination.DefaultPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "user": "600/min",
        "anon": "60/min",
        "auth_login": "10/min",
        "auth_register": "10/hour",
        "auth_password_reset": "5/hour",
        "auth_verify": "10/hour",
        "api_key_create": "10/hour",
        "webhook_test": "30/hour",
        "csv_import": "10/hour",
        "contact": "5/hour",
    },
    "EXCEPTION_HANDLER": "apps.api.exceptions.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "ChainSentinel API",
    "DESCRIPTION": (
        "Real-time wallet, token, approval, and smart-contract monitoring across EVM "
        "networks. Authenticate with a session cookie (browser) or an API key via the "
        "`X-Api-Key` header (integrations)."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_SETTINGS": {"persistAuthorization": True, "displayRequestDuration": True},
}

# ---------------------------------------------------------------------------
# CORS / CSRF
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [FRONTEND_URL]
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env_csv(
    "CSRF_TRUSTED_ORIGINS", ["http://localhost:3026", "http://localhost:8212"]
)
CSRF_COOKIE_HTTPONLY = False  # SPA must read it to echo the header back
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = SECURE_COOKIES
SESSION_COOKIE_SECURE = SECURE_COOKIES
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 12  # admin sessions: 12h

# ---------------------------------------------------------------------------
# Cache / Redis
# ---------------------------------------------------------------------------
REDIS_URL = env_str("REDIS_URL", "redis://localhost:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "cs",
        # Hard socket timeouts: a dead Redis must fail fast, never hang requests.
        "OPTIONS": {
            "socket_connect_timeout": 3,
            "socket_timeout": 3,
        },
    }
}

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env_str("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = env_str("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_TASK_ACKS_LATE = True  # tasks re-queue if a worker dies mid-run
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "apps.events.tasks.*": {"queue": "engine"},
    "apps.chains.tasks.*": {"queue": "engine"},
    "apps.webhooks.tasks.*": {"queue": "delivery"},
    "apps.notifications.tasks.*": {"queue": "delivery"},
    "apps.alerts.tasks.*": {"queue": "default"},
    "apps.audit.tasks.*": {"queue": "default"},
}
CELERY_BROKER_TRANSPORT_OPTIONS = {"visibility_timeout": 3600}

# ---------------------------------------------------------------------------
# Email — SMTP from environment variables only
# ---------------------------------------------------------------------------
EMAIL_HOST = env_str("SMTP_HOST", "")
EMAIL_PORT = env_int("SMTP_PORT", 587)
EMAIL_HOST_USER = env_str("SMTP_USER", "")
EMAIL_HOST_PASSWORD = env_str("SMTP_PASSWORD", "")
EMAIL_USE_TLS = env_bool("SMTP_USE_TLS", True)
DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL", "ChainSentinel <no-reply@localhost>")
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
PLATFORM_ALERT_EMAILS = env_csv("PLATFORM_ALERT_EMAILS", [])

# ---------------------------------------------------------------------------
# Static files (admin, DRF browsable, swagger)
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# ChainSentinel engine / platform configuration
# ---------------------------------------------------------------------------
ENGINE_MAX_BLOCKS_PER_POLL = env_int("ENGINE_MAX_BLOCKS_PER_POLL", 10)
ENGINE_REORG_WINDOW = 64  # recent block hashes kept per chain for reorg detection
ENGINE_RPC_TIMEOUT_SECONDS = env_int("ENGINE_RPC_TIMEOUT_SECONDS", 15)
ENGINE_PROVIDER_FAILURE_THRESHOLD = 5  # consecutive failures before marked unhealthy
ENGINE_PROVIDER_BACKOFF_BASE = 30  # seconds; doubles per consecutive failure
ENGINE_PROVIDER_BACKOFF_CAP = 1800
WS_SUBSCRIPTIONS_ENABLED = env_bool("WS_SUBSCRIPTIONS_ENABLED", False)

WEBHOOK_ENCRYPTION_KEY = env_str("WEBHOOK_ENCRYPTION_KEY", "")
WEBHOOK_ALLOWED_PORTS = [
    int(p) for p in env_csv("WEBHOOK_ALLOWED_PORTS", ["80", "443", "8000", "8080", "8443"])
]
WEBHOOK_DEFAULT_TIMEOUT = 10
WEBHOOK_MAX_RETRIES_CAP = 10
WEBHOOK_BACKOFF_BASE_SECONDS = 60
WEBHOOK_BACKOFF_CAP_SECONDS = 3600 * 6
WEBHOOK_USER_AGENT = "ChainSentinel-Webhooks/1.0"

RETENTION_EVENTS_DAYS = env_int("RETENTION_EVENTS_DAYS", 90)
RETENTION_WEBHOOK_DELIVERIES_DAYS = env_int("RETENTION_WEBHOOK_DELIVERIES_DAYS", 30)
RETENTION_HEALTH_LOGS_DAYS = env_int("RETENTION_HEALTH_LOGS_DAYS", 14)
RETENTION_WORKER_LOGS_DAYS = env_int("RETENTION_WORKER_LOGS_DAYS", 14)

ABI_MAX_BYTES = 512 * 1024  # 512 KB uploaded/pasted ABI limit
CSV_IMPORT_MAX_BYTES = 1024 * 1024  # 1 MB
CSV_IMPORT_MAX_ROWS = 500

SEED_DEMO_PASSWORD = env_str("SEED_DEMO_PASSWORD", "DemoPass123!")

# ---------------------------------------------------------------------------
# Logging — structured-ish, secrets redacted via filter
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"redact": {"()": "apps.audit.logging_filters.RedactSecretsFilter"}},
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "filters": ["redact"],
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"level": "WARNING"},
        "chainsentinel": {"level": "INFO"},
    },
}
