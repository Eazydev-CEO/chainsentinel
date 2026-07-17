# Security

## Principles

1. **Read-only by design** — no private keys are ever collected or stored; the platform
   cannot sign or send transactions. RPC usage is query-only.
2. **Secrets live in the environment** — no credentials in code or Git; `.env` is ignored.
3. **Tenant isolation is enforced in one place** — `apps/api/permissions.py` +
   `apps/api/workspace.py`; every workspace queryset filters through membership.

## Authentication & session controls

| Control | Implementation |
|---------|----------------|
| Password rules | Django validators: ≥10 chars, not common, not numeric, not similar to email |
| Session transport | JWT in **HttpOnly** cookies (`cs_access` 15 min / `cs_refresh` 14 d, path-restricted); never localStorage |
| CSRF | Cookie-sourced writes run Django's CSRF check (`X-CSRFToken` double-submit) |
| Refresh rotation | `ROTATE_REFRESH_TOKENS` + blacklist; replayed old tokens are rejected |
| Device management | `UserSession` per refresh family: list, revoke one, revoke others; password change/reset revokes sessions |
| Email verification | Signed, expiring tokens (48 h); monitor/webhook/API-key writes require a verified email |
| Password reset | Signed token embeds a password-hash fragment → single-use; responses never reveal account existence |
| Rate limiting | DRF scoped throttles (login 10/min, register 10/h, reset 5/h, key-create 10/h, CSV 10/h, contact 5/h) + global user/anon rates + nginx `limit_req` in front |

## Authorization

* Roles: owner > admin > analyst > viewer with per-view minimums and per-action overrides
  (e.g. analysts may acknowledge/resolve/annotate alerts, only owners manage API keys and
  delete workspaces, admins cannot manage other admins).
* Object-level checks confirm `obj.workspace == active workspace`; cross-tenant IDs 404.
* API keys: SHA-256 hashed at rest, constant-time compared, workspace-bound, scope-limited,
  revocable, expirable, `last_used` tracked; malformed/revoked/expired keys are rejected.
* Suspended workspaces are blocked at the permission layer and skipped by the engine.

## Input validation

* EVM addresses: strict EIP-55 (mixed-case inputs must checksum-validate — catches typos).
* ABI uploads: size-capped (512 KB), JSON-parsed defensively, structural validation per
  entry; malformed ABIs return clean 400s and can never crash ingestion (decode failures
  store the raw log + error).
* CSV import: size (1 MB) and row (500) caps, encoding detection, header validation,
  per-row serializer validation, in-file and DB duplicate detection, atomic row creation.
* Webhook URLs: see SSRF section.
* All other input passes DRF serializers with explicit field constraints.

## Webhook egress (SSRF defence)

Scheme allowlist (http/https), port allowlist, credential-bearing URLs rejected, hostname
blocklist (localhost, cloud metadata), IP-literal and DNS-resolved targets checked against
loopback/private/link-local/multicast/reserved/metadata ranges (including IPv4-mapped IPv6),
redirects never followed, validation at save **and** send time.
**Known residual risk:** a DNS-rebinding TOCTOU window between resolution and connection
remains (connection pinning to resolved IPs with TLS/SNI is out of v1 scope). Mitigations:
re-validation per attempt, no redirects, port restrictions. Documented deliberately.

## Platform hardening

* Security headers on every Django response (strict CSP for the API, relaxed only for
  admin/swagger) + Next.js headers + nginx headers; `X-Frame-Options: DENY`, HSTS in prod.
* DEBUG off in production settings; unhandled errors show Django's plain 500 page — no
  stack traces; errors are recorded to `SystemErrorLog` with **redacted** tracebacks.
* Log redaction: a logging filter plus recursive metadata scrubbing remove API keys, JWTs,
  webhook secrets and password-like fields from logs, audit metadata and stored errors.
* Webhook secrets encrypted at rest (Fernet, key from env); API responses never include
  them after creation.
* Audit log records auth events, membership changes, monitor/webhook/key lifecycle, alert
  actions, CSV imports — with actor, IP, user agent and redacted metadata.
* Docker: non-root containers, prod compose exposes only nginx, DB/Redis have no published
  ports, healthchecks everywhere.
* CORS: restricted to the configured frontend origin with credentials.

## Reporting

Report vulnerabilities via the contact form or `PLATFORM_ALERT_EMAILS` operators. Please do
not test SSRF/throttle bypasses against hosted instances you don't own.
