import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Features" };

const GROUPS = [
  {
    eyebrow: "Wallet monitoring",
    title: "Every movement, classified",
    items: [
      ["Native & token transfers", "Incoming, outgoing or both — with EIP-55 validation, per-monitor confirmation depth and minimum-value filters."],
      ["NFT transfers", "ERC-721 Transfer events with token IDs, matched to your wallets automatically."],
      ["Approval security", "New approvals, changed allowances, revocations and ApprovalForAll operator grants — the events attackers rely on."],
      ["Large-movement thresholds", "Set a threshold per monitor; matching events are flagged and severity-escalated automatically."],
    ],
  },
  {
    eyebrow: "Contract monitoring",
    title: "Your ABI, decoded live",
    items: [
      ["ABI upload & validation", "Paste or upload any ABI JSON — malformed input is rejected safely, never crashes ingestion."],
      ["Event selection", "Pick exactly which events to monitor; signatures and topic hashes are generated for you."],
      ["Indexed-parameter filters", "Only care about a specific sender or pool? Filter on any indexed event parameter."],
      ["Raw log preservation", "If decoding fails, the raw log is stored and displayed with the decode error."],
    ],
  },
  {
    eyebrow: "Alerting",
    title: "Signal, not noise",
    items: [
      ["Rule engine", "Filter by monitor, chain, event type, token, amounts, addresses and topic. Trigger on confirmed or reverted events."],
      ["Cooldowns & grouping", "Suppress repeats with per-fingerprint cooldowns; fold bursts into one grouped alert with a counter."],
      ["Five severity levels", "Info to critical, with per-user in-app and email severity preferences."],
      ["Alert lifecycle", "Acknowledge, resolve, annotate with internal notes — the full timeline is preserved."],
    ],
  },
  {
    eyebrow: "Delivery",
    title: "Alerts that reach systems",
    items: [
      ["Signed webhooks", "HMAC SHA-256 signatures with timestamp headers. Delivery logs record status, latency and failure reasons."],
      ["Retries & replay", "Exponential backoff up to your retry limit, plus one-click replay of any delivery."],
      ["SSRF-safe egress", "Private networks, localhost and cloud metadata endpoints are blocked at save time and again at send time."],
      ["Email & in-app", "Critical alert emails, failed-webhook notices, provider-outage warnings and daily summaries."],
    ],
  },
  {
    eyebrow: "Platform",
    title: "Multi-tenant and operable",
    items: [
      ["Workspaces & roles", "Owner, admin, analyst, viewer — strict object-level isolation enforced on every query."],
      ["Scoped API keys", "Read or read/write keys bound to a workspace, hashed at rest, shown exactly once."],
      ["RPC failover", "Prioritized providers with health probes, exponential backoff and automatic recovery."],
      ["Audit logging", "Every sensitive action is recorded with actor, IP and metadata — visible to workspace admins."],
    ],
  },
];

export default function FeaturesPage() {
  return (
    <div className="container py-5">
      <div className="text-center mb-5">
        <span className="section-eyebrow">Features</span>
        <h1 className="fw-bold mt-2">Everything a monitoring desk needs</h1>
        <p className="text-secondary mx-auto" style={{ maxWidth: 620 }}>
          ChainSentinel is a full monitoring pipeline — ingestion, decoding, confirmation
          tracking, alerting and delivery — not just a notification bot.
        </p>
      </div>

      {GROUPS.map((group) => (
        <section className="mb-5" key={group.title}>
          <span className="section-eyebrow">{group.eyebrow}</span>
          <h2 className="fw-bold mt-1 mb-4">{group.title}</h2>
          <div className="row g-4">
            {group.items.map(([title, body]) => (
              <div className="col-md-6" key={title}>
                <div className="cs-card p-4 h-100">
                  <h6 className="fw-semibold">{title}</h6>
                  <p className="text-secondary small mb-0">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}

      <div className="text-center pt-3">
        <Link href="/register" className="btn btn-primary btn-lg px-5">
          Create your workspace →
        </Link>
      </div>
    </div>
  );
}
