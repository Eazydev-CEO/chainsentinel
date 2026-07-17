# Changelog

All notable changes to ChainSentinel are documented here.
Format: [Keep a Changelog](https://keepachangelog.com) · Versioning: SemVer.

## [0.1.0] — 2026-07-06

First production-ready release: the complete platform, end to end.

### Added — platform
- Multi-tenant workspaces with owner/admin/analyst/viewer roles, invitations, strict
  object-level isolation and suspension controls.
- Authentication: registration with auto-workspace, email verification (signed tokens),
  login/logout/refresh with HttpOnly-cookie JWTs + rotation/blacklist, CSRF enforcement,
  password reset (single-use tokens) and change, device/session management, throttling.
- Workspace-scoped API keys (hashed, scoped read/write, shown once, revocable, expiring).

### Added — monitoring
- Chain registry for 6 EVM networks + their testnets; per-chain confirmations/block time.
- RPC providers with priorities, health probes, exponential-backoff failover, rate-limit
  awareness and outage notifications. Optional WebSocket newHeads accelerator (`listen_ws`).
- Wallet monitors: EIP-55 validation, duplicate prevention, direction/category/token/
  min-value filters, large-transfer thresholds with severity escalation, CSV import/export
  with row-level reports, pause/resume, stats & activity.
- Contract monitors: safe ABI parsing/dedup, event extraction with signatures + topic0,
  event selection, indexed-parameter filters, decode-with-raw-fallback.
- Engine: ordered block processing under per-chain locks, idempotent event writes,
  confirmation tracking with per-event snapshots, reorg detection/revert/rewind with
  incident records, crash-safe checkpoints, workspace-suspension awareness.

### Added — alerting & delivery
- Alert rules (filters incl. virtual `large_transfer`, trigger on confirmed/reverted),
  cooldowns, grouping/debounce with occurrence counters, severity inheritance.
- Alerts with acknowledge/resolve, internal notes, full timelines.
- In-app notifications with per-user severity/email preferences; critical-alert,
  failed-webhook, provider-outage and daily-summary emails (SMTP from env; console in dev).
- Webhooks: HMAC SHA-256 (`t=…,v1=…`) with timestamp headers, SSRF-guarded egress
  (validated at save and send), encrypted secrets with one-time display + regeneration,
  exponential retries persisted across restarts, exhaustion notifications, test pings,
  full delivery history with replay.

### Added — product surface
- Premium dark public site (home, features, chains, how-it-works, pricing placeholder,
  docs, contact wired to email, privacy, terms) — responsive from 320 px.
- Dashboard: overview cards + charts from real aggregates, analytics page, event explorer
  with deep filtering and detail timelines, monitor management UIs, alert center, webhook
  console, notifications center, provider health, settings (profile/security/workspace/
  members/API keys) — loading skeletons, empty states, ultrawide max-width.
- Versioned REST API with OpenAPI schema + Swagger UI, consistent error envelope,
  pagination/filtering/throttling; analytics endpoints; public contact endpoint.
- Django admin for all models with operational actions (retry webhooks, pause/resume
  monitors, disable providers, retry alert processing, suspend workspaces, activate chains).

### Added — engineering
- 175-test pytest suite (mocked Web3, no network): validators, ABI, engine incl. reorg and
  restart recovery, failover, alert rules incl. cooldown/debounce, webhooks incl. SSRF and
  backoff, permissions, API keys, CSV, auth incl. CSRF.
- Docker: dev + production compose (7 services), non-root images, healthchecks, nginx
  reverse proxy with security headers and rate shielding, Next standalone build.
- Documentation set: architecture, database, API, webhooks, security, environment,
  deployment, testing, runbook, supported chains + CONTRIBUTING.md and PROJECTFLOW.md.
- Dev-only labelled seed data (`seed_dev`, refuses outside DEBUG).

### Deliberate v1 placeholders
- Billing (plan field + pricing page only), Telegram/Slack alert actions ("coming soon"),
  WS subscriptions as optional accelerator, DNS-rebinding TOCTOU documented in SECURITY.md.
