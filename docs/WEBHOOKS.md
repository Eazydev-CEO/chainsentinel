# Webhooks

Outbound, HMAC-signed HTTP POSTs to endpoints you configure per workspace.

## Event catalog

| Type | Fired when |
|------|-----------|
| `alert.triggered` | An alert rule matched a confirmed event |
| `alert.resolved` | An alert was resolved in the dashboard/API |
| `event.confirmed` | A blockchain event reached its confirmation depth |
| `monitor.paused` | A monitor was paused (admin action) |
| `provider.unhealthy` | An RPC provider was marked unhealthy |
| `test.ping` | You pressed “Send test” |

Endpoints subscribe to a subset; unsubscribed types are never delivered.

## Delivery format

```
POST <your-url>
Content-Type: application/json
User-Agent: ChainSentinel-Webhooks/1.0
X-ChainSentinel-Event: alert.triggered
X-ChainSentinel-Delivery: ep:4:alert:123:triggered
X-ChainSentinel-Timestamp: 1751790000
X-ChainSentinel-Signature: t=1751790000,v1=<hex hmac-sha256>
```

Body:
```json
{
  "id": "ep:4:alert:123:triggered",
  "type": "alert.triggered",
  "created_at": "2026-07-06T10:00:00+00:00",
  "workspace_id": 1,
  "data": { "alert_id": 123, "title": "…", "severity": "high", "event": { "tx_hash": "0x…", "…": "…" } }
}
```

## Verifying signatures

The signature is `HMAC_SHA256(secret, f"{timestamp}.{raw_body}")` in hex.

```python
import hashlib, hmac, time

def verify(secret: str, headers, raw_body: bytes, tolerance=300) -> bool:
    timestamp = headers["X-ChainSentinel-Timestamp"]
    parts = dict(p.split("=", 1) for p in headers["X-ChainSentinel-Signature"].split(","))
    if abs(time.time() - int(timestamp)) > tolerance:
        return False  # replay protection
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts["v1"])
```

Always verify against the **raw** request body, before any JSON re-serialization.

## Secrets

Generated server-side (`whsec_…`), encrypted at rest with Fernet
(`WEBHOOK_ENCRYPTION_KEY`), returned exactly once at creation or regeneration, never
retrievable afterwards. Regenerating invalidates the old secret immediately.

## Retries, replay, history

* 2xx = delivered. 3xx counts as failure — **redirects are never followed** (SSRF).
* Failures retry with exponential backoff (`60s × 2^attempt`, capped 6 h) up to the
  endpoint's retry limit (max 10). Retries are persisted (`next_retry_at`) and survive
  worker restarts.
* When retries exhaust, workspace members are notified (in-app + opted-in email) and the
  delivery is marked `exhausted`.
* Every attempt records status code, latency and a safe failure reason. Any delivery can be
  **replayed** from the dashboard or `POST /webhook-deliveries/{id}/replay/`.
* Respond `2xx` quickly (<10 s default timeout) and process async on your side; dedupe by
  the `id` field — replays share the original payload with a new delivery id suffix.

## SSRF protection (what we refuse to call)

`http(s)` only; ports restricted to `WEBHOOK_ALLOWED_PORTS`; credentials-in-URL rejected;
`localhost`/`*.localhost` and metadata hostnames blocked; the hostname is DNS-resolved and
**every** resolved address must be public (loopback, RFC1918, link-local, IPv4-mapped IPv6,
multicast, reserved and cloud-metadata IPs are all refused). Validation runs at save time
and again at each send. Residual DNS-rebinding TOCTOU is documented in SECURITY.md.
