import Link from "next/link";

const CHAINS = ["Ethereum", "BNB Smart Chain", "Polygon", "Base", "Arbitrum", "Optimism"];

const USE_CASES = [
  {
    icon: "🏦",
    title: "Treasury monitoring",
    body: "Watch every inflow and outflow of company wallets with confirmation-aware alerts and full audit trails.",
  },
  {
    icon: "🐋",
    title: "Whale-wallet tracking",
    body: "Track large holders across chains. Get notified the moment a threshold-breaking transfer confirms.",
  },
  {
    icon: "📈",
    title: "DeFi wallet monitoring",
    body: "Follow positions, token flows and NFT movements across your DeFi operations wallets in one place.",
  },
  {
    icon: "🛡",
    title: "Approval security alerts",
    body: "Detect new, changed and unlimited token approvals — and confirm revocations actually landed.",
  },
  {
    icon: "📜",
    title: "Contract event tracking",
    body: "Upload an ABI, pick the events, filter on indexed parameters. Decoded payloads, raw logs preserved.",
  },
  {
    icon: "🏛",
    title: "DAO treasury monitoring",
    body: "Give contributors read access with roles, keep analysts annotating alerts, notify the whole team.",
  },
];

const FEATURES = [
  {
    icon: "⛓",
    title: "Six EVM networks",
    body: "Ethereum, BSC, Polygon, Base, Arbitrum and Optimism — with per-chain confirmation policies and testnet support.",
  },
  {
    icon: "🔁",
    title: "RPC failover built in",
    body: "Prioritized providers, health checks, exponential backoff and automatic failover. Reorg-aware ingestion.",
  },
  {
    icon: "⚡",
    title: "Real-time alert rules",
    body: "Amount thresholds, address filters, approval spikes, severity levels, cooldowns, debounce and grouping.",
  },
  {
    icon: "⇄",
    title: "Signed webhooks",
    body: "HMAC SHA-256 signatures, timestamps, delivery logs, automatic retries with backoff, one-click replay.",
  },
  {
    icon: "👥",
    title: "Team workspaces",
    body: "Owner, admin, analyst and viewer roles with strict tenant isolation and full audit logging.",
  },
  {
    icon: "🔑",
    title: "API-first",
    body: "Versioned REST API with scoped API keys and OpenAPI docs. Everything the dashboard does, you can automate.",
  },
];

export default function HomePage() {
  return (
    <>
      {/* Hero */}
      <section className="hero-gradient border-bottom" style={{ borderColor: "var(--cs-border)" }}>
        <div className="container py-5">
          <div className="row align-items-center g-5 py-lg-4">
            <div className="col-lg-6">
              <span className="section-eyebrow">EVM monitoring infrastructure</span>
              <h1 className="display-5 fw-bold mt-2 mb-3" style={{ letterSpacing: "-0.02em" }}>
                Never miss a transaction that{" "}
                <span style={{ color: "var(--cs-accent)" }}>matters</span>.
              </h1>
              <p className="lead text-secondary mb-4" style={{ maxWidth: 540 }}>
                ChainSentinel watches wallets, tokens, approvals and smart contracts across EVM
                networks in real time — deduplicated, confirmation-aware and reorg-safe — then
                alerts your team by dashboard, email and signed webhooks.
              </p>
              <div className="d-flex flex-wrap gap-2 mb-4">
                <Link href="/register" className="btn btn-primary btn-lg px-4">
                  Create your workspace
                </Link>
                <Link href="/how-it-works" className="btn btn-outline-secondary btn-lg px-4">
                  See how it works
                </Link>
              </div>
              <div className="d-flex flex-wrap gap-3 small text-secondary">
                <span>✓ Read-only — no private keys, ever</span>
                <span>✓ Testnet-first development</span>
                <span>✓ Self-hostable</span>
              </div>
            </div>
            <div className="col-lg-6">
              <div className="terminal-mock shadow-lg" role="img" aria-label="Live monitoring feed example">
                <div className="terminal-head">
                  <span style={{ background: "#ff5d5d" }} />
                  <span style={{ background: "#ffb84f" }} />
                  <span style={{ background: "#2fbf71" }} />
                  <code className="ms-2 text-secondary">chainsentinel · live feed</code>
                </div>
                <pre>
{`▸ block 21_442_308 on `}<span className="t-blue">ethereum</span>{` (12 confs)
  `}<span className="t-green">native_received</span>{`  14.2 ETH → treasury.eth
  alert `}<span className="t-amber">HIGH</span>{` "Large inflow" → email ✓ webhook ✓

▸ block 21_442_309
  `}<span className="t-green">approval_created</span>{`  USDC → 0x1111…2582
  amount: `}<span className="t-amber">unlimited</span>{` — alert `}<span className="t-amber">CRITICAL</span>{`
  webhook sig `}<span className="t-blue">v1=hmac-sha256</span>{` delivered 201 in 184ms

▸ reorg check … parent hashes verified ✓
▸ provider p99 latency 82ms · failover armed`}
                </pre>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Chains */}
      <section className="py-5">
        <div className="container text-center">
          <span className="section-eyebrow">Supported networks</span>
          <h2 className="fw-bold mt-2 mb-4">Six EVM chains, mainnet & testnet</h2>
          <div className="d-flex flex-wrap justify-content-center gap-2 mb-3">
            {CHAINS.map((chain) => (
              <span className="chain-pill" key={chain}>
                <span className="status-dot dot-green" aria-hidden="true" />
                {chain}
              </span>
            ))}
          </div>
          <p className="text-secondary small">
            Local development runs against Sepolia, BSC Testnet, Amoy, Base Sepolia, Arbitrum
            Sepolia and OP Sepolia. <Link href="/chains">See chain details →</Link>
          </p>
        </div>
      </section>

      {/* What it monitors + workflow */}
      <section className="py-5 border-top" style={{ borderColor: "var(--cs-border)" }}>
        <div className="container">
          <div className="row g-5">
            <div className="col-lg-6">
              <span className="section-eyebrow">What it watches</span>
              <h2 className="fw-bold mt-2 mb-3">Wallets and contracts, decoded</h2>
              <p className="text-secondary mb-4">
                Point ChainSentinel at any address. It ingests blocks in order, matches your
                monitors, decodes ERC-20 / ERC-721 transfers and approvals, tracks
                confirmations, and survives reorgs without duplicating or losing events.
              </p>
              <ul className="list-unstyled d-grid gap-2 text-secondary">
                <li>✓ Native, ERC-20 and NFT transfers — incoming, outgoing or both</li>
                <li>✓ Token approvals: created, changed, revoked, operator approvals</li>
                <li>✓ Large-movement thresholds with automatic severity escalation</li>
                <li>✓ Custom contract events from your ABI with indexed-parameter filters</li>
                <li>✓ Raw logs preserved even when decoding fails</li>
              </ul>
            </div>
            <div className="col-lg-6">
              <span className="section-eyebrow">Monitoring workflow</span>
              <h2 className="fw-bold mt-2 mb-4">From block to notification</h2>
              <div>
                <div className="workflow-step" data-step="1">
                  <strong>Ingest</strong>
                  <p className="text-secondary small mb-0">
                    Workers poll every chain through prioritized RPC providers with health
                    checks and exponential-backoff failover.
                  </p>
                </div>
                <div className="workflow-step" data-step="2">
                  <strong>Match & decode</strong>
                  <p className="text-secondary small mb-0">
                    Transactions and logs are matched to your monitors, decoded against ABIs,
                    and stored exactly once with idempotency keys.
                  </p>
                </div>
                <div className="workflow-step" data-step="3">
                  <strong>Confirm</strong>
                  <p className="text-secondary small mb-0">
                    Events wait for your configured confirmation depth. Reorged blocks revert
                    cleanly and reprocess from the fork point.
                  </p>
                </div>
                <div className="workflow-step" data-step="4">
                  <strong>Alert & deliver</strong>
                  <p className="text-secondary small mb-0">
                    Rules evaluate severity, cooldown and grouping — then fan out to the
                    dashboard, email and HMAC-signed webhooks with retries.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Use cases */}
      <section className="py-5 border-top" style={{ borderColor: "var(--cs-border)" }}>
        <div className="container">
          <div className="text-center mb-5">
            <span className="section-eyebrow">Use cases</span>
            <h2 className="fw-bold mt-2">Built for teams that watch the chain</h2>
          </div>
          <div className="row g-4">
            {USE_CASES.map((useCase) => (
              <div className="col-md-6 col-lg-4" key={useCase.title}>
                <div className="cs-card p-4 h-100">
                  <div className="feature-icon mb-3">{useCase.icon}</div>
                  <h5 className="fw-semibold">{useCase.title}</h5>
                  <p className="text-secondary small mb-0">{useCase.body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Dashboard preview */}
      <section className="py-5 border-top" style={{ borderColor: "var(--cs-border)" }}>
        <div className="container">
          <div className="text-center mb-4">
            <span className="section-eyebrow">Dashboard</span>
            <h2 className="fw-bold mt-2">Your on-chain operations room</h2>
            <p className="text-secondary">
              Live metrics, an event explorer, alert timelines and provider health — driven by
              real database records, not vanity numbers.
            </p>
          </div>
          <div className="glass-card p-4 shadow-lg">
            <div className="row g-3">
              {[
                ["Active monitors", "12"],
                ["Events today", "1,284"],
                ["Critical alerts", "2"],
                ["Webhook success", "99.4%"],
              ].map(([label, value]) => (
                <div className="col-6 col-lg-3" key={label}>
                  <div className="stat-card">
                    <div className="stat-label">{label}</div>
                    <div className="stat-value">{value}</div>
                    <div className="stat-sub">example workspace</div>
                  </div>
                </div>
              ))}
            </div>
            <div className="table-scroll mt-3">
              <table className="table table-cs">
                <thead>
                  <tr>
                    <th>Event</th><th>Chain</th><th>Amount</th><th>Status</th><th>Severity</th>
                  </tr>
                </thead>
                <tbody className="small">
                  <tr>
                    <td>Native received</td><td>Ethereum</td><td>14.20 ETH</td>
                    <td><span className="badge-status st-confirmed">confirmed</span></td>
                    <td><span className="badge-severity severity-high">high</span></td>
                  </tr>
                  <tr>
                    <td>Approval created</td><td>Base</td><td className="mono">unlimited USDC</td>
                    <td><span className="badge-status st-confirmed">confirmed</span></td>
                    <td><span className="badge-severity severity-critical">critical</span></td>
                  </tr>
                  <tr>
                    <td>Contract event · Swap</td><td>Arbitrum</td><td>2,410.55 USDT</td>
                    <td><span className="badge-status st-pending">pending</span></td>
                    <td><span className="badge-severity severity-medium">medium</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>

      {/* Features grid */}
      <section className="py-5 border-top" style={{ borderColor: "var(--cs-border)" }}>
        <div className="container">
          <div className="text-center mb-5">
            <span className="section-eyebrow">Platform</span>
            <h2 className="fw-bold mt-2">Production-grade from day one</h2>
          </div>
          <div className="row g-4">
            {FEATURES.map((feature) => (
              <div className="col-md-6 col-lg-4" key={feature.title}>
                <div className="d-flex gap-3">
                  <div className="feature-icon flex-shrink-0">{feature.icon}</div>
                  <div>
                    <h6 className="fw-semibold mb-1">{feature.title}</h6>
                    <p className="text-secondary small mb-0">{feature.body}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* API section */}
      <section className="py-5 border-top" style={{ borderColor: "var(--cs-border)" }}>
        <div className="container">
          <div className="row g-5 align-items-center">
            <div className="col-lg-5">
              <span className="section-eyebrow">API & webhooks</span>
              <h2 className="fw-bold mt-2 mb-3">Integrate in an afternoon</h2>
              <p className="text-secondary">
                Scoped API keys, filtered event queries and verified webhook payloads. Every
                delivery is signed with HMAC SHA-256 and includes a timestamp header — replay
                attacks bounce off.
              </p>
              <Link href="/docs" className="btn btn-outline-secondary">
                Read the docs
              </Link>
            </div>
            <div className="col-lg-7">
              <div className="terminal-mock">
                <div className="terminal-head">
                  <code className="text-secondary">verify_webhook.py</code>
                </div>
                <pre>
{`sig_header = request.headers["X-ChainSentinel-Signature"]
timestamp  = request.headers["X-ChainSentinel-Timestamp"]

expected = hmac.new(
    secret.encode(),
    f"{timestamp}.{raw_body}".encode(),
    hashlib.sha256,
).hexdigest()

assert hmac.compare_digest(expected, sig_header.split("v1=")[1])`}
                </pre>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-5 border-top hero-gradient" style={{ borderColor: "var(--cs-border)" }}>
        <div className="container text-center py-4">
          <h2 className="fw-bold mb-3">Start watching your wallets in minutes</h2>
          <p className="text-secondary mb-4">
            Create a workspace, add a wallet, set a rule. Free while in early access.
          </p>
          <Link href="/register" className="btn btn-primary btn-lg px-5">
            Create your workspace →
          </Link>
        </div>
      </section>
    </>
  );
}
