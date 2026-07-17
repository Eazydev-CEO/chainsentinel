# Supported chains

Seeded by `python manage.py seed_dev` (mainnets **inactive** by policy; testnets active and
used for local development).

## Matrix

| Network | Chain ID | Native | Default confirmations | Block time | Explorer | Env prefix |
|---------|---------:|--------|----------------------:|-----------:|----------|------------|
| Ethereum | 1 | ETH | 12 | ~12 s | etherscan.io | `RPC_ETHEREUM` |
| **Ethereum Sepolia** | 11155111 | ETH | 6 | ~12 s | sepolia.etherscan.io | `RPC_ETHEREUM_SEPOLIA` |
| BNB Smart Chain | 56 | BNB | 15 | ~3 s | bscscan.com | `RPC_BSC` |
| **BSC Testnet** | 97 | tBNB | 10 | ~3 s | testnet.bscscan.com | `RPC_BSC_TESTNET` |
| Polygon | 137 | POL | 30 | ~2.1 s | polygonscan.com | `RPC_POLYGON` |
| **Polygon Amoy** | 80002 | POL | 15 | ~2.1 s | amoy.polygonscan.com | `RPC_POLYGON_AMOY` |
| Base | 8453 | ETH | 12 | ~2 s | basescan.org | `RPC_BASE` |
| **Base Sepolia** | 84532 | ETH | 6 | ~2 s | sepolia.basescan.org | `RPC_BASE_SEPOLIA` |
| Arbitrum One | 42161 | ETH | 20 | ~0.3 s | arbiscan.io | `RPC_ARBITRUM` |
| **Arbitrum Sepolia** | 421614 | ETH | 10 | ~0.3 s | sepolia.arbiscan.io | `RPC_ARBITRUM_SEPOLIA` |
| Optimism | 10 | ETH | 12 | ~2 s | optimistic.etherscan.io | `RPC_OPTIMISM` |
| **OP Sepolia** | 11155420 | ETH | 6 | ~2 s | sepolia-optimism.etherscan.io | `RPC_OPTIMISM_SEPOLIA` |

Confirmation defaults are deliberately conservative; users can override per monitor.

## Adding an RPC provider

**Via env + seed (dev):** set `RPC_<PREFIX>_HTTP` (and optionally `_WS`) in `.env`, run
`python manage.py seed_dev` — the `primary-env` provider activates.

**Via admin (any env):** Admin → RPC providers → Add: chain, name, HTTPS endpoint, optional
WS endpoint, priority (lower = tried first), rate limit/second. Health checks pick it up
within a minute. Multiple providers per chain give automatic failover.

## Adding a new chain

1. Admin → Chains → Add (name, slug, chain ID, symbol, explorer URL, testnet flag,
   confirmations, block time) — or extend the `CHAINS` list in
   `apps/chains/management/commands/seed_dev.py` for repeatable environments.
2. Add ≥1 active RPC provider.
3. Set `is_active=True`. Polling starts on the next scheduler tick, anchored just behind
   the current tip (no historical backfill).
4. Any EVM-compatible chain works — the engine only relies on standard JSON-RPC
   (`eth_blockNumber`, `eth_getBlockByNumber`, `eth_getLogs`, `eth_call`).

## Enabling a mainnet (deliberate action)

Mainnets ship disabled to prevent accidental use of production RPC quotas. To enable:
provide a real `RPC_<CHAIN>_HTTP`, create/activate the provider, then set the chain
active in admin. Review provider rate limits and your alert-rule noise before doing so.
