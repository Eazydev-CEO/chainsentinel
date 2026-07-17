import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "How it works" };

const STEPS = [
  {
    title: "Connect chains through your RPC providers",
    body: "Add HTTPS endpoints per chain (testnets first). Providers get priorities, health probes every minute, and automatic exponential-backoff failover. No provider? That chain simply pauses — nothing breaks.",
  },
  {
    title: "Create monitors",
    body: "Wallet monitors validate and checksum addresses, prevent duplicates per workspace, and let you choose direction, event categories, token filters, minimum values and large-transfer thresholds. Contract monitors take an ABI, extract its events, and subscribe to the ones you pick — with optional indexed-parameter filters.",
  },
  {
    title: "Workers ingest blocks in order",
    body: "Celery workers hold a per-chain lock, poll new blocks, match native transactions to your wallets, and pull token-standard and contract logs with targeted eth_getLogs queries. Every event gets an idempotency key — retries, restarts and reprocessing can never duplicate it.",
  },
  {
    title: "Confirmations and reorg safety",
    body: "Events sit in PENDING until your configured confirmation depth is reached. The engine keeps a rolling window of block hashes; if the canonical chain diverges, affected events are marked REVERTED, the incident is logged for review, and ingestion rewinds to the fork point.",
  },
  {
    title: "Rules evaluate, alerts fan out",
    body: "On confirmation, workspace rules run: filters on type, amounts, addresses and tokens; cooldowns and grouping keep noise down. Matching events produce alerts with severity, an audit timeline, acknowledgement and resolution flows.",
  },
  {
    title: "Notifications reach your systems",
    body: "In-app notifications respect per-user severity preferences. Emails go out for critical alerts, failed webhooks, provider outages and daily summaries. Webhooks are HMAC-SHA-256-signed, timestamped, retried with backoff, logged per attempt, and replayable.",
  },
];

export default function HowItWorksPage() {
  return (
    <div className="container py-5" style={{ maxWidth: 880 }}>
      <div className="text-center mb-5">
        <span className="section-eyebrow">Architecture</span>
        <h1 className="fw-bold mt-2">How ChainSentinel works</h1>
        <p className="text-secondary">
          A real ingestion pipeline — not a cron job wrapped around an explorer API.
        </p>
      </div>

      <div className="mb-5">
        {STEPS.map((step, index) => (
          <div className="workflow-step" data-step={index + 1} key={step.title}>
            <h5 className="fw-semibold">{step.title}</h5>
            <p className="text-secondary mb-0">{step.body}</p>
          </div>
        ))}
      </div>

      <div className="terminal-mock mb-5">
        <div className="terminal-head">
          <code className="text-secondary">architecture</code>
        </div>
        <pre>
{`Next.js dashboard ──► Django REST API ──► PostgreSQL
                          │    ▲               ▲
                    enqueue│    │source of truth│
                          ▼    │               │
                   Celery workers ─────────────┘
                   ├─ poll blocks (per-chain lock)
                   ├─ decode & dedupe events
                   ├─ confirmations + reorg handling
                   ├─ alert rules → notifications/email
                   └─ signed webhook delivery (+retries)
                          │
                          ▼
                EVM chains via failover RPC providers`}
        </pre>
      </div>

      <div className="text-center">
        <Link href="/register" className="btn btn-primary btn-lg px-5">
          Create your workspace →
        </Link>
      </div>
    </div>
  );
}
