# PROJECTFLOW.md — ChainSentinel Build Flow

Living document tracking what exists, how it fits together, and what state each feature is
in. Update this whenever behaviour changes. Companion to `CONTRIBUTING.md` (rules) and
`docs/ARCHITECTURE.md` (deep design).

## 1. Product summary

ChainSentinel monitors EVM wallets and smart contracts in real time: native/ERC-20/NFT
transfers, token approvals and revocations, custom ABI-decoded contract events, large
movements, RPC provider health and webhook delivery status. Events are deduplicated,
confirmation-tracked, reorg-aware, and fan out to alert rules → in-app notifications,
emails, and HMAC-signed webhooks. Multi-tenant workspaces with Owner/Admin/Analyst/Viewer
roles. Built to become a paid SaaS (plan field + billing placeholder already modelled).

## 2. System flow (end to end)

```
                        ┌─────────────────────────────────────────────┐
                        │                  Browser                    │
                        └───────────────┬─────────────────────────────┘
                                        │ HTTPS (nginx in prod, Next rewrites in dev)
              ┌─────────────────────────┴───────────────┐
              │ Next.js (public site + dashboard SPA)    │  no DB access, ever
              └─────────────────────────┬───────────────┘
                                        │ /api/v1/* (HttpOnly cookie JWT or API key)
              ┌─────────────────────────┴───────────────┐
              │ Django + DRF (source of truth)           │──── PostgreSQL
              │ auth · workspaces · monitors · events    │──── Redis (cache/throttle)
              │ alerts · webhooks · notifications · audit│
              └─────────────────────────┬───────────────┘
                                        │ enqueue (Redis broker)
      ┌─────────────────────────────────┴──────────────────────────────┐
      │ Celery workers + Beat                                          │
      │  schedule_chain_polls ─► poll_chain (lock) ─► process_block    │
      │     ├─ reorg check (stored hash ring vs canonical chain)       │
      │     ├─ native tx matching (wallet monitors)                    │
      │     ├─ eth_getLogs: token transfers/approvals + contract subs  │
      │     └─ BlockchainEvent rows (idempotency_key, PENDING)         │
      │  confirm_pending_events ─► CONFIRMED ─► evaluate_alert_rules   │
      │     └─ Alert (cooldown/debounce/grouping) ─► actions:          │
      │          in-app Notification · email · WebhookDelivery         │
      │  deliver_webhook (HMAC, SSRF-guarded, exponential retry)       │
      │  check_provider_health · send_daily_summaries · cleanup        │
      └────────────────────────────────────────────────────────────────┘
                    │ RPC via failover client (priority + backoff)
              EVM chains (testnets by default; mainnets seeded inactive)
```

## 3. Feature status

| # | Feature | Backend | Frontend | Tests | Status |
|---|---------|---------|----------|-------|--------|
| 1 | Public website (12 pages) | n/a | app/(public) | build | ✅ Complete |
| 2 | Auth (register/login/verify/reset/sessions) | apps/accounts | app/(auth) | tests/test_auth.py | ✅ Complete |
| 3 | Workspaces + roles + invitations | apps/workspaces | app/app/settings | tests/test_permissions.py | ✅ Complete |
| 4 | Chains + RPC providers + failover | apps/chains | app/app/providers | tests/test_rpc_failover.py | ✅ Complete |
| 5 | Wallet monitors (+CSV import/export) | apps/monitors | app/app/monitors/wallets | tests/test_csv_import.py, test_validators.py | ✅ Complete |
| 6 | Contract monitors + ABI parsing | apps/monitors | app/app/monitors/contracts | tests/test_abi.py | ✅ Complete |
| 7 | Monitoring engine (poll/confirm/reorg/dedupe) | apps/events + engine | — | tests/test_engine.py | ✅ Complete |
| 8 | Alert rules engine (cooldown/debounce/grouping) | apps/alerts | app/app/alert-rules | tests/test_alert_rules.py | ✅ Complete |
| 9 | Alerts (ack/resolve/notes/timeline) | apps/alerts | app/app/alerts | tests/test_alert_rules.py | ✅ Complete |
| 10 | Webhooks (HMAC/SSRF/retry/replay/test) | apps/webhooks | app/app/webhooks | tests/test_webhooks.py | ✅ Complete |
| 11 | Notifications (bell/prefs/emails) | apps/notifications | components/notifications | via engine tests | ✅ Complete |
| 12 | Dashboard + analytics (real DB metrics) | apps/api/analytics | app/app | build | ✅ Complete |
| 13 | Event explorer + detail | apps/events | app/app/events | tests/test_engine.py | ✅ Complete |
| 14 | API keys + scopes | apps/accounts | app/app/settings/api-keys | tests/test_api_keys.py | ✅ Complete |
| 15 | REST API v1 + OpenAPI/Swagger | apps/api | — | all API tests | ✅ Complete |
| 16 | Django Admin + custom actions | all apps admin.py | — | — | ✅ Complete |
| 17 | Audit logs | apps/audit | event/alert timelines | in API tests | ✅ Complete |
| 18 | Docker (dev + prod) + nginx | docker/ | — | compose config | ✅ Complete |
| 19 | Documentation set | docs/ | /docs page | — | ✅ Complete |
| 20 | Seed data (dev-only, labelled) | seed_dev command | — | — | ✅ Complete |

## 4. Key design decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Auth transport | SimpleJWT in HttpOnly cookies + CSRF header on unsafe methods | XSS-resistant; SPA-friendly; refresh rotation + blacklist |
| Workspace scoping | `?workspace=<id>` param / `X-Workspace-Id` header + membership permission classes | explicit, cache-friendly, no URL nesting explosion |
| Event identity | `idempotency_key` = chain:block:tx:log:type:monitor (unique index) | dedupe across retries/restarts/reorg reprocessing |
| Block progress | `BlockCheckpoint` per chain + recent-hash ring buffer | crash-safe resume; reorg detection window |
| Confirmations | per-event `confirmations_required` snapshot (monitor override else chain default) | rule changes don't retro-affect in-flight events |
| Reorg handling | walk stored hashes back to fork point; revert events; rewind checkpoint; `ReorgIncident` row | correctness over speed; admin-reviewable |
| RPC transport | HTTP polling primary; optional WS `newHeads` trigger (`listen_ws` command, off by default) | Celery-compatible reliability; WS is an accelerator only |
| Webhook secrets | Fernet-encrypted at rest (key derived from `WEBHOOK_ENCRYPTION_KEY`), write-only API | must sign later, must never leak via API |
| Webhook safety | scheme/port allowlist + DNS resolution + private/metadata IP block + no redirects | SSRF defence per docs/SECURITY.md |
| Amounts | wei in `DecimalField(78,0)`; token decimals cached on event | no float loss; display-side formatting |
| Tags/JSON | `JSONField` (not ArrayField) | portable across PG/SQLite (tests), flexible |
| Frontend↔API in dev | Next.js rewrites `/api/*` → Django :8212 | same-origin cookies, no CORS pain; nginx does it in prod |

## 5. Django apps

`accounts` (user, profile, sessions, api keys, email flows) · `workspaces` (workspace,
membership, invitations) · `chains` (chains, rpc providers, health, failover client) ·
`monitors` (wallet/contract monitors, ABI, subscriptions, CSV) · `events` (checkpoints,
blockchain events, reorg incidents, engine) · `alerts` (rules, alerts, notes, evaluation) ·
`webhooks` (endpoints, deliveries, signer, SSRF guard) · `notifications` (in-app + email +
prefs) · `audit` (audit log, system errors, worker job logs) · `api` (routing, permissions,
throttles, pagination, errors, analytics, schema).

## 6. Celery task map

| Task | Trigger | Notes |
|------|---------|-------|
| `engine.schedule_chain_polls` | beat / 10s | enqueues `poll_chain` for active chains with active monitors |
| `engine.poll_chain` | scheduled | Redis lock per chain; reorg check → process blocks in order → checkpoint |
| `engine.confirm_pending_events` | beat / 30s | promotes PENDING→CONFIRMED at depth; enqueues alert evaluation |
| `alerts.evaluate_event_alerts` | on confirm | rule match → cooldown/debounce/group → Alert + actions |
| `notifications.send_notification_email` | on alert/system | SMTP from env only |
| `webhooks.deliver_webhook` | on alert/event/test | HMAC sign, SSRF-guard, record attempt |
| `webhooks.retry_due_deliveries` | beat / 60s | exponential backoff via `next_retry_at` (restart-safe) |
| `chains.check_provider_health` | beat / 60s | latency probe, consecutive-failure tracking, outage notifications |
| `notifications.send_daily_summaries` | beat / daily 07:00 UTC | per-workspace digest to opted-in members |
| `audit.cleanup_old_records` | beat / daily 03:30 UTC | retention windows from env |

## 7. Environment & running

See `docs/ENVIRONMENT.md` for every variable, `.env.example` for the template, and
`README.md` for quickstart. TL;DR: `cp .env.example .env` → `docker compose up --build` →
frontend :3026, API :8212, Swagger at `/api/v1/docs/`, admin at `/admin/`.
`python manage.py seed_dev` loads labelled demo data (dev only).

## 8. Deliberate v1 scope cuts (documented, not hidden)

- Billing is a placeholder (plan field + pricing page); no payment provider wired.
- Telegram/Slack alert actions are placeholders (modelled + UI-visible as "coming soon").
- WebSocket subscriptions are an optional poll-trigger (`listen_ws`), not the primary path.
- NFT support = ERC-721 Transfer/Approval events (no metadata fetching).
- Token metadata (symbol/decimals) is best-effort with Redis caching; non-standard tokens
  fall back to raw wei display.
- DNS-rebinding TOCTOU on webhooks is mitigated (resolve-then-validate, no redirects) but
  not fully pinned; documented in docs/SECURITY.md.

## 9. Change log pointers

See `CHANGELOG.md`. Initial release: v0.1.0 — full platform as described above.
