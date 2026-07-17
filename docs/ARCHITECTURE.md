# Architecture

## Components

```
Browser ──► nginx (prod) ──► Next.js  (public site + dashboard SPA)
                      └────► Django + DRF  (/api/v1, /admin, /static)
                                   │
                                   ├── PostgreSQL   ← the single source of truth
                                   ├── Redis        ← cache, throttles, locks, Celery broker
                                   └── Celery workers + Beat
                                            │
                                            └── EVM chains via failover RPC providers
```

* **Next.js** never touches the database. In development it proxies `/api/*` to Django via a
  rewrite (same-origin cookies, no CORS pain); in production nginx routes `/api` directly.
* **Django** owns auth, tenancy, configuration, storage and the REST API.
* **Celery** owns every long-running or blockchain-facing job. HTTP handlers never poll
  chains, send emails, or deliver webhooks inline.

## Django apps

| App | Owns |
|-----|------|
| `accounts` | User, profile, sessions (refresh-token families), API keys, auth endpoints |
| `workspaces` | Workspace, membership+roles, invitations |
| `chains` | Chain registry, RPC providers, health logs, **failover client** |
| `monitors` | Wallet/contract monitors, ABI documents, event subscriptions, CSV import |
| `events` | Block checkpoints, blockchain events, reorg incidents, **engine**, poll/confirm tasks |
| `alerts` | Alert rules, alerts, notes, evaluation service |
| `webhooks` | Endpoints, deliveries, HMAC signer, SSRF guard, delivery/retry tasks |
| `notifications` | In-app notifications, preferences, email rendering/delivery, daily digest |
| `audit` | Audit log, system errors, worker job logs, retention cleanup |
| `api` | Versioned routing, workspace permissions, pagination, error envelope, analytics |

## The monitoring engine

Entry points: `apps/events/tasks.py` + `apps/events/engine.py`.

1. **`schedule_chain_polls`** (Beat, every `ENGINE_POLL_INTERVAL_SECONDS`) enqueues
   `poll_chain(chain_id)` for every active chain that has at least one active monitor in a
   non-suspended workspace.
2. **`poll_chain`** takes a Redis lock (`lock:poll-chain:<id>`) so exactly one worker polls a
   chain at a time — restarts and horizontal scaling stay safe. It builds a `ChainEngine`
   with an `RpcClient`.
3. **Reorg check** — the checkpoint stores a ring of the last `ENGINE_REORG_WINDOW` block
   hashes. If the newest stored hash no longer matches the canonical chain, the engine walks
   backwards to the fork point, marks affected events `REVERTED`, records a `ReorgIncident`,
   rewinds the checkpoint, and reprocesses forward.
4. **Block processing** (`checkpoint+1 … min(latest, +ENGINE_MAX_BLOCKS_PER_POLL)` in order):
   * native transfers: full-transaction block scan matched against wallet monitors
     (direction, min value, large-transfer threshold);
   * token events: one `eth_getLogs` per block filtered on the Transfer/Approval/
     ApprovalForAll topics, matched by participant address; ERC-20 vs ERC-721 disambiguated
     by topic count; approvals classified created/changed/revoked;
   * contract subscriptions: `eth_getLogs` by monitored address (chunked), matched by
     `topic0`, decoded against the stored ABI fragment, indexed-parameter filters applied;
     decode failures preserve the raw log with the error.
   * Every event is written with an **idempotency key**
     (`chain:block:tx:log:type:monitorkind:monitorid`, unique index) via `get_or_create` —
     retries and reprocessing can never duplicate.
   * The checkpoint advances **inside the same transaction** as the block's events: a crash
     mid-block reprocesses the whole block and dedupes.
5. **`confirm_pending_events`** (Beat 30s + after each poll) promotes `PENDING` events whose
   depth ≥ per-event `confirmations_required` (snapshotted from the monitor/chain at
   detection). Confirmation triggers `evaluate_event_alerts` and `event.confirmed` webhooks.
6. **Alert evaluation** (`apps/alerts/services.py`): per-rule match (monitor/chain/type/
   token/amount/address/topic filters) → exact dedupe (rule+event) → grouping window (folds
   repeats into one alert with a counter) → cooldown (Redis TTL per fingerprint) → alert +
   actions (in-app, email, webhook).

## RPC failover (`apps/chains/client.py`)

Providers are tried in priority order. Timeouts, connection failures, HTTP 429 and invalid
responses are classified, recorded on the provider row (consecutive failures, health state,
last reason) and put the provider into an exponential-backoff window in Redis
(`base 30s × 2^failures`, capped 30 min). A per-second local token counter respects each
provider's configured rate limit. When every provider fails, `AllProvidersFailedError` is
raised, logged once per 15 minutes per chain, and polling simply retries next tick — the
checkpoint guarantees nothing is skipped. Health probes run every minute
(`check_provider_health`) and raise chain-outage notifications when all providers are down.

**Never** does the client rotate proxies, spoof identity, or evade provider restrictions.

## WebSocket accelerator (optional)

`python manage.py listen_ws` (guarded by `WS_SUBSCRIPTIONS_ENABLED=false` by default)
subscribes to `newHeads` on providers exposing a WS endpoint and enqueues `poll_chain`
immediately when heads arrive. It is purely a latency optimization — HTTP polling remains
the correctness mechanism and continues regardless of WS state.

## Restart & idempotency guarantees

* Celery: `acks_late=True`, `reject_on_worker_lost=True` — a killed worker re-queues its task.
* Poll lock prevents duplicate concurrent polling; the checkpoint prevents gaps and rewinds.
* Events, alerts, notifications and webhook deliveries all carry unique idempotency/dedupe
  keys enforced by the database.
* Webhook retries are scheduled via `next_retry_at` + a Beat scanner (not `countdown`), so
  scheduled retries survive restarts; stale `PENDING` deliveries older than 10 minutes are
  rescued by the same scanner.

## Multi-tenancy

Every domain row carries `workspace_id`. API access resolves the active workspace
(`X-Workspace-Id` header / `?workspace=` / body field), verifies membership and role
(`apps/api/permissions.py`), and filters querysets through it. API keys are hard-bound to
their workspace (write scope ≈ admin, read scope ≈ viewer). Suspended workspaces are blocked
at the permission layer and skipped by the engine.
