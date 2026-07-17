# Environment variables

Copy `.env.example` → `.env`. Everything secret comes from here — nothing is hardcoded.

## Core Django

| Variable | Default | Notes |
|----------|---------|-------|
| `DJANGO_SETTINGS_MODULE` | `config.settings.development` | `…production` / `…test` |
| `DJANGO_SECRET_KEY` | dev placeholder | **must** be long & random in prod (startup fails otherwise) |
| `DJANGO_DEBUG` | `true` (dev) | never `true` in production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,backend` | comma separated |
| `FRONTEND_URL` | `http://localhost:3026` | used in email links, CORS |
| `BACKEND_URL` | `http://localhost:8212` | informational |
| `CSRF_TRUSTED_ORIGINS` | localhost pair | add `https://yourdomain.com` in prod |

## Database & Redis

| Variable | Default | Notes |
|----------|---------|-------|
| `POSTGRES_DB/USER/PASSWORD/HOST/PORT` | chainsentinel / … / localhost / 5432 | compose overrides HOST to `postgres` |
| `REDIS_URL` | `redis://redis:6379/0` | cache, locks, throttles |
| `CELERY_BROKER_URL` | `redis://redis:6379/1` | task queue |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/2` | results |

## Email (SMTP only — required for verification/reset/alert emails)

`SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_USE_TLS` (true),
`DEFAULT_FROM_EMAIL`, `PLATFORM_ALERT_EMAILS` (comma-separated operator addresses for
outage/system/contact mail). In development with `SMTP_HOST` empty, emails print to the
console.

## Security

| Variable | Default | Notes |
|----------|---------|-------|
| `WEBHOOK_ENCRYPTION_KEY` | derived from SECRET_KEY (dev) | **set explicitly in prod**: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` — rotating it orphans stored secrets |
| `JWT_ACCESS_MINUTES` / `JWT_REFRESH_DAYS` | 15 / 14 | token lifetimes |
| `SECURE_COOKIES` | `false` | `true` behind HTTPS (prod settings force it) |
| `WEBHOOK_ALLOWED_PORTS` | `80,443,8000,8080,8443` | outbound webhook ports |

## Engine

| Variable | Default | Notes |
|----------|---------|-------|
| `ENGINE_MAX_BLOCKS_PER_POLL` | 10 | catch-up burst size per tick |
| `ENGINE_POLL_INTERVAL_SECONDS` | 10 | beat scheduling tick |
| `ENGINE_RPC_TIMEOUT_SECONDS` | 15 | per-request timeout |
| `WS_SUBSCRIPTIONS_ENABLED` | `false` | enables the optional `listen_ws` accelerator |
| `RETENTION_EVENTS_DAYS` | 90 | event retention |
| `RETENTION_WEBHOOK_DELIVERIES_DAYS` | 30 | delivery-log retention |
| `RETENTION_HEALTH_LOGS_DAYS` / `RETENTION_WORKER_LOGS_DAYS` | 14 | ops-log retention |

## RPC endpoints

Per network pairs consumed by `seed_dev` (blank ⇒ provider stays inactive):

```
RPC_ETHEREUM_SEPOLIA_HTTP / _WS      RPC_ETHEREUM_HTTP
RPC_BSC_TESTNET_HTTP / _WS           RPC_BSC_HTTP
RPC_POLYGON_AMOY_HTTP / _WS          RPC_POLYGON_HTTP
RPC_BASE_SEPOLIA_HTTP / _WS          RPC_BASE_HTTP
RPC_ARBITRUM_SEPOLIA_HTTP / _WS      RPC_ARBITRUM_HTTP
RPC_OPTIMISM_SEPOLIA_HTTP / _WS      RPC_OPTIMISM_HTTP
```

Use **testnets locally**. Mainnet chains are seeded inactive; enabling them is a deliberate
admin action.

## Frontend

| Variable | Default | Notes |
|----------|---------|-------|
| `NEXT_PUBLIC_API_BASE_URL` | `` (same origin) | leave empty with rewrites/nginx |
| `API_INTERNAL_URL` | `http://backend:8212` | server-side proxy target in dev/docker |

## Seed

`SEED_DEMO_PASSWORD` (default `DemoPass123!`) — password for the dev-only demo users.
