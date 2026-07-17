# Testing

## Running

```bash
cd backend
pytest                    # whole suite (~4s, 175 tests)
pytest tests/test_engine.py -k reorg -v
```

Settings: `config.settings.test` — SQLite, eager Celery (tasks run inline), locmem cache and
email, throttles neutralized, fixed Fernet key. **No test touches the network**: Web3 is
mocked through `tests/fakes.py`, webhook HTTP through monkeypatched `requests.post`, DNS
through monkeypatched `socket.getaddrinfo`.

Frontend: `npm run build` is the gate (strict TypeScript compile of every page).

## Suite map (what each file proves)

| File | Coverage |
|------|----------|
| `test_validators.py` | EVM address validation, EIP-55 normalization, bad-checksum rejection |
| `test_abi.py` | ABI parsing (incl. wrappers/garbage/size caps), event extraction, signature + topic0 generation (checked against the canonical Transfer hash), tuple canonicalization, log decoding incl. mismatches and indexed-dynamic hashing |
| `test_engine.py` | checkpoint init/advance/ring, native & ERC-20/721 detection, direction/min-value/token filters, large-transfer flag + severity bump, approval created→changed→revoked lifecycle, **dedupe across crash-rewind**, contract subscription decode + indexed filters, confirmation depth incl. per-monitor override, **reorg revert/rewind/reprocess + incident record**, suspended-workspace skip |
| `test_rpc_failover.py` | failover on timeout/429/invalid-response, error classification, backoff skip, unhealthy threshold, success reset, local rate-limit spillover, all-providers-failed |
| `test_alert_rules.py` | rule matching matrix (type/status/amounts/large/spender/chain), dedupe per event, **cooldown**, **grouping/debounce** (fold + single notification + resolved-alerts excluded), severity inheritance, webhook action delivery record |
| `test_webhooks.py` | HMAC determinism + header format + verify, **SSRF matrix** (loopback/private/link-local/metadata/IPv6/mapped-IPv6/schemes/ports/credentials/DNS-rebind), delivery success with signature verification and no-redirects, **exponential backoff schedule**, exhaustion + notification, send-time SSRF recheck, disabled endpoint, terminal-success idempotency, retry scanner (due/future/stale-pending rescue), replay linkage, secret shown-once/regeneration |
| `test_permissions.py` | workspace-context requirement, non-member rejection, cross-tenant 404s, role matrix (viewer/analyst/admin/owner), member management edge cases (admin↛admin, owner protection, self-leave), suspended workspace |
| `test_api_keys.py` | header auth, implicit workspace, scope enforcement, tampered/revoked/expired keys, foreign-workspace denial, user-only endpoints, last-used tracking, lifecycle API incl. unverified-email block |
| `test_csv_import.py` | happy path, row-level errors with valid rows kept, in-file + DB duplicates, header/row/size caps, no partial rows, API endpoint + file-type check, export→import round-trip |
| `test_auth.py` | registration (workspace + cookies + verification email), duplicate/weak-password rejection, login/me, **CSRF enforcement on cookie writes**, refresh rotation with old-token replay rejection, logout, session listing, verification round-trip, unverified-user write block, reset-token single-use, no account enumeration |

## Fakes

`tests/fakes.py` provides `FakeChainData` (an in-memory canonical chain you mutate:
`add_block/add_tx/add_log/reorg_from`), `FakeWeb3`/`FailingWeb3` for the failover client,
and `MiniClient` to drop into `ChainEngine`. Build scenarios in data, not in mocks-of-mocks.

## Adding tests

New engine/webhook/permission behaviour **requires** tests (see CONTRIBUTING.md). Prefer:
fixture-driven pytest functions, one behavioural assertion cluster per test, monkeypatch at
the boundary (`requests.post`, `socket.getaddrinfo`, `RpcClient`) — never inside domain
logic.
