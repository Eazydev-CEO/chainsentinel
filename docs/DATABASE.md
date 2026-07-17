# Database

PostgreSQL is the only supported production database (tests run on SQLite with the same
models — no Postgres-only field types are used; tags/JSON use `JSONField`).

## Model inventory

### accounts
| Model | Purpose | Notable fields / constraints |
|-------|---------|------------------------------|
| `User` | Email-login user | `email` unique; `is_email_verified` |
| `UserProfile` | Extra profile data | 1:1 user |
| `UserSession` | Device session per refresh-token family | `refresh_jti` unique; revoke ⇒ blacklist |
| `ApiKey` | Workspace-scoped API key | `prefix` unique; SHA-256 `hashed_key`; `scopes` JSON |
| (SimpleJWT) `OutstandingToken`/`BlacklistedToken` | Refresh rotation + revocation | — |

### workspaces
| Model | Purpose | Notable |
|-------|---------|---------|
| `Workspace` | Tenant | `slug` unique; `suspended_at`; plan placeholder |
| `WorkspaceMember` | Membership+role | unique `(workspace, user)`; roles owner/admin/analyst/viewer |
| `WorkspaceInvitation` | Email invite | token unique; expiry; revoke/accept stamps |

### chains
| Model | Purpose | Notable |
|-------|---------|---------|
| `Chain` | Network registry | `chain_id` unique; `required_confirmations`; `is_testnet`; `is_active` |
| `RpcProvider` | Endpoint per chain | priority; health fields; rate limit; index `(chain, is_active, priority)` |
| `RpcProviderHealthLog` | Probe history | latency, block number, error |

### monitors
| Model | Purpose | Notable |
|-------|---------|---------|
| `WalletMonitor` | Address watcher | unique `(workspace, chain, address)`; direction; event categories; min value; large threshold; confirmations override |
| `ContractMonitor` | Contract watcher | unique `(workspace, chain, address)`; selected events; topic filters |
| `ContractAbi` | Validated ABI doc | unique `(workspace, sha256)` — deduped |
| `EventSubscription` | Concrete (monitor,event) | unique `(monitor, signature)`; `topic0` indexed; abi fragment; indexed filters |
| `MonitorCsvImport` | Import report | row-level results JSON |

### events
| Model | Purpose | Notable |
|-------|---------|---------|
| `BlockCheckpoint` | Per-chain progress | 1:1 chain; recent-hash ring for reorg detection |
| `BlockchainEvent` | Detected occurrence | **`idempotency_key` unique**; status pending/confirmed/reverted/failed/ignored; amounts as `Decimal(78,0)` wei; decoded + raw JSON |
| `ReorgIncident` | Reorg record | fork block, depth, events reverted |

### alerts
| Model | Purpose | Notable |
|-------|---------|---------|
| `AlertRule` | Condition → actions | filters (monitor/chain/type/token/amount/addresses/topic); cooldown; group window; action flags; telegram/slack placeholders |
| `Alert` | Fired alert | **`dedupe_key` unique** (rule+event); `group_key` indexed; count; ack/resolve stamps |
| `AlertNote` | Internal note | author, body |

### webhooks
| Model | Purpose | Notable |
|-------|---------|---------|
| `WebhookEndpoint` | Destination | Fernet-encrypted secret; subscribed event types; retry/timeout config; last-status fields |
| `WebhookDelivery` | One logical delivery | **`idempotency_key` unique**; attempts; response status/time; `next_retry_at` indexed; `replay_of` self-FK |

### notifications
| Model | Purpose |
|-------|---------|
| `Notification` | Per-user in-app notice (severity, link, read stamp) |
| `NotificationPreference` | Per-user severity/email preferences |

### audit
| Model | Purpose |
|-------|---------|
| `AuditLog` | Immutable action record (actor, target, metadata redacted, IP) |
| `SystemErrorLog` | Platform errors (redacted traceback) |
| `WorkerJobLog` | Task runs (status, duration, detail) |

## Required indexes (spec → implementation)

| Requirement | Where |
|-------------|-------|
| chain + block number | `BlockchainEvent Index(chain, block_number)` |
| transaction hash | `BlockchainEvent Index(tx_hash)` |
| wallet address | `BlockchainEvent Index(from_address)`, `Index(to_address)`; `MonitorBase.address` db_index |
| contract address | `BlockchainEvent Index(token_address)` + monitor address index |
| event topic | `BlockchainEvent Index(topic0)`; `EventSubscription.topic0` db_index |
| workspace + created date | `BlockchainEvent Index(workspace, created_at)`; same on monitors/alerts/audit |
| alert status | `Alert Index(workspace, status)` |
| webhook delivery status | `WebhookDelivery Index(workspace, status)` + `status`, `next_retry_at` db_index |
| event processing status | `BlockchainEvent Index(status, chain)` |

## Conventions

* Addresses are stored EIP-55 checksummed (`CharField(42)`); comparisons use `iexact`/lower.
* Raw on-chain amounts are `DecimalField(max_digits=78, decimal_places=0)` — full uint256
  range without float loss; token decimals are cached per event for display.
* Timestamps are timezone-aware UTC (`USE_TZ=True`).
* Migrations live with each app (`apps/*/migrations/0001_initial.py`).
