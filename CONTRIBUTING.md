# Contributing to ChainSentinel

Engineering guide for anyone working in this repository. Read this and
`PROJECT_FLOW/PROJECTFLOW.md` before making changes.

## Stack (fixed — do not substitute)

| Layer      | Technology |
|------------|------------|
| Frontend   | Next.js (App Router) + TypeScript + React + Bootstrap 5 + SCSS + React Hook Form + Zod + Chart.js |
| Backend    | Python 3.12+ / Django / Django REST Framework / drf-spectacular / SimpleJWT (HttpOnly cookies) |
| Data       | PostgreSQL (all persistent data) / Redis (cache, queues, locks, rate limits ONLY) |
| Workers    | Celery + Celery Beat + Web3.py |
| Infra      | Docker Compose: frontend, backend, celery_worker, celery_beat, postgres, redis, nginx |

Do not introduce: Vue, Nuxt, Tailwind, Prisma, BullMQ, Next.js API routes as a backend, or
long-running listeners inside HTTP request handlers.

## Architecture invariants

1. Next.js talks to Django **only** through the versioned REST API (`/api/v1/...`). It never
   touches PostgreSQL or Redis.
2. Django (DRF) is the single source of truth: auth, workspaces/roles, monitors, events,
   alerts, webhooks, API keys, audit logs.
3. All blockchain work (block polling, log decoding, confirmations, reorg handling, alert
   evaluation, email, webhook delivery) runs in **Celery workers** — never in HTTP handlers.
4. Celery tasks are **idempotent** and safe to re-run after a restart. Blockchain events,
   alerts, notifications and webhook deliveries all carry idempotency/dedupe keys enforced
   by unique DB constraints.
5. Strict workspace isolation: every workspace-scoped queryset is filtered through
   membership checks (`apps/api/permissions.py`). Never expose an object across workspaces.
6. Auth tokens live in **HttpOnly cookies** (`cs_access` / `cs_refresh`), never localStorage.
   Cookie-authenticated unsafe requests require a CSRF header.
7. No private keys are ever stored. No transactions are ever sent. Read-only RPC access.
8. Mainnet chains are seeded **inactive**; local development uses testnets and placeholder
   RPC env vars. Never hardcode provider URLs or API keys in code.
9. Secrets come from environment variables only. Webhook secrets are encrypted at rest and
   never returned by the API after creation.
10. RPC failover is responsible: exponential backoff, provider health tracking, respect for
    rate limits. No proxy rotation or restriction bypasses — ever.

## Development workflow

```bash
# Backend (from backend/, venv active)
pip install -r requirements/development.txt
python manage.py migrate
python manage.py seed_dev          # dev-only demo data (refuses to run in production)
python manage.py runserver 8212

# Workers
celery -A config worker -l info
celery -A config beat -l info

# Frontend (from frontend/)
npm install && npm run dev         # http://localhost:3026, /api proxied to :8212

# Everything at once
docker compose up --build

# Tests
cd backend && pytest               # config.settings.test: SQLite, eager Celery, locmem
cd frontend && npm run build       # type-check + production build
```

## Conventions

- **Backend:** services hold business logic (`apps/*/services.py`), tasks are thin wrappers
  (`apps/*/tasks.py`), serializers validate, views stay skinny. Addresses are stored
  EIP-55 checksummed; comparisons are case-insensitive. Amounts are stored in wei as
  `DecimalField(max_digits=78)`. Every model change ships with a migration.
- **Frontend:** `lib/api.ts` is the only fetch layer; feature calls live in `services/`;
  shared types in `types/`. Forms = React Hook Form + Zod schema. Styling = Bootstrap 5 +
  SCSS design tokens in `styles/` (dark theme, `--cs-*` variables). User-facing confirm/
  prompt dialogs go through `lib/dialogs.ts`.
- **Errors:** API errors always render the envelope
  `{"error": {"code", "message", "details"}}` (see `apps/api/exceptions.py`).
- **Testing:** meaningful tests over coverage theatre. Web3 is always mocked
  (`tests/fakes.py`). New engine/webhook/permission logic requires tests.
- **Docs:** update `PROJECT_FLOW/PROJECTFLOW.md` status tables and relevant `docs/*.md`
  whenever behaviour changes. `CHANGELOG.md` records notable changes.

## Hard rules

- Do not commit secrets, `.env` files, RPC keys, or credentials of any kind.
- Do not fabricate blockchain data, dashboard metrics, or "fake activity". Dashboards read
  real database records. Seed data is dev-only and clearly labelled `[DEMO]`.
- Do not claim a feature is complete unless it is wired end-to-end
  (UI → API → DB → worker → notification/webhook where applicable).
- Do not weaken security controls (SSRF guards, throttles, permission checks, HMAC
  signing) to "make something work".

## Pull requests

Keep PRs focused; include tests for engine/webhook/permission changes; run the full test
suite and a frontend build before requesting review.
