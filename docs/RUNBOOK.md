# Runbook — operating ChainSentinel

Admin console: `/admin/` (staff accounts). Most incidents are resolved from there.

## Dashboards to check first

| Where | What it tells you |
|-------|-------------------|
| Admin → Worker job logs | Poll/confirm/delivery task outcomes, durations, errors |
| Admin → System error logs | Redacted platform errors (engine, api, webhooks, alerts) |
| Admin → RPC providers / health logs | Provider state, consecutive failures, latency |
| Admin → Reorg incidents | Fork depth, events reverted, when |
| App → /app/providers | Same provider health, user-visible |

## Incidents

### A chain stopped ingesting
1. Admin → RPC providers: any healthy provider for that chain?
   * All unhealthy → provider outage. Check `last_failure_reason` (`rate_limited`?
     `timeout`?). Add/enable another provider (env var + seed, or admin), or wait —
     backoff recovers automatically and polling resumes **from the checkpoint**, so no
     events are lost inside the retention/reorg window.
2. Chain active? (Admin → Chains → `is_active`).
3. Any active monitors on it? The scheduler skips chains with none.
4. Worker alive? `docker compose logs celery_worker`, and Beat running (exactly one).

### Provider keeps flapping / rate-limited
Admin → RPC providers → lower its priority or **Disable selected providers**; raise
`rate_limit_per_second` accuracy; add a second provider. Use **Reset health counters**
after fixing credentials.

### Webhook deliveries failing
1. Admin → Webhook deliveries: filter status `retrying`/`exhausted`; read
   `failure_reason` (`blocked: …` = SSRF guard, `http_4xx/5xx` = receiver, `timeout`…).
2. Receiver fixed? Select deliveries → **Retry selected** (exhausted ones reset and
   re-queue), or use dashboard **Replay**.
3. Secret mismatch on the receiver → regenerate from the dashboard and update the receiver.

### Reorg incident logged
Normal on fast chains. Verify: affected events show `reverted`, replacement events exist
for the new branch, checkpoint advanced past the fork. Deep reorgs beyond the stored window
rewind conservatively to the window start — expect a burst of reprocessed (deduped) blocks.

### Abusive workspace
Admin → Workspaces → **Suspend selected workspaces**. Suspension blocks API access
(members see "suspended"), stops engine matching and API keys immediately. Lift with
**Unsuspend**.

### Monitor misbehaving (e.g. absurd thresholds, spam)
Admin → Wallet/Contract monitors → **Pause selected monitors** (user sees it paused, can
be resumed either side). `error_count`/`last_error` show validation issues.

### Stuck alert evaluation / missed alerts
Admin → Blockchain events → select confirmed events → **Retry alert processing** —
evaluation is idempotent (per rule+event dedupe), safe to re-run.

### Queue backlog
`docker compose exec redis redis-cli -n 1 llen engine` (and `delivery`, `default`).
Scale workers: `docker compose up -d --scale celery_worker=3`. Locks/idempotency make this
safe. Beat stays singular.

### Emails not arriving
Console backend prints to logs when `SMTP_HOST` empty (dev). In prod check
`send_email_task` retries in Worker job logs and SMTP credentials in `.env`.

## Routine maintenance

* Retention cleanup runs nightly (03:30 UTC) — tune `RETENTION_*` env vars.
* Daily summaries go out 07:00 UTC to opted-in users.
* Nightly Postgres dumps (see DEPLOYMENT.md) + protect `.env`.

## Safe restarts

`docker compose restart celery_worker backend` any time: polling resumes from checkpoints,
in-flight tasks re-queue (`acks_late`), scheduled webhook retries persist in the DB, and
idempotency keys prevent duplicates. This is tested (`test_engine.py`,
`test_webhooks.py::TestRetryScanner`).
