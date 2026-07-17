import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Documentation" };

const SECTIONS = [
  {
    title: "Getting started",
    items: [
      ["Create a workspace", "Register, verify your email, and your first workspace is ready. Invite teammates with owner/admin/analyst/viewer roles."],
      ["Add a wallet monitor", "Monitors validate EIP-55 checksums, prevent duplicates, and start from the current block — no backfill surprises."],
      ["Set an alert rule", "Combine event types, amount bounds and address filters. Choose in-app, email and webhook actions."],
    ],
  },
  {
    title: "API",
    items: [
      ["Authentication", "Browser sessions use secure HttpOnly cookies. Integrations use scoped API keys via the X-Api-Key header."],
      ["OpenAPI reference", "Interactive Swagger UI with every endpoint, schema and example lives at /api/v1/docs/."],
      ["Rate limits", "Per-user and per-endpoint throttles protect the platform; 429 responses include a wait hint."],
    ],
  },
  {
    title: "Webhooks",
    items: [
      ["Verify signatures", "Each delivery carries X-ChainSentinel-Timestamp and X-ChainSentinel-Signature (t=…,v1=…). Recompute the HMAC SHA-256 of `timestamp.body` with your endpoint secret and compare."],
      ["Retries & replay", "Failed deliveries retry with exponential backoff up to your limit. Replay any delivery from the dashboard."],
      ["Event catalog", "alert.triggered, alert.resolved, event.confirmed, monitor.paused, provider.unhealthy, test.ping."],
    ],
  },
];

export default function DocsPage() {
  return (
    <div className="container py-5" style={{ maxWidth: 960 }}>
      <div className="text-center mb-5">
        <span className="section-eyebrow">Documentation</span>
        <h1 className="fw-bold mt-2">ChainSentinel docs</h1>
        <p className="text-secondary">
          Guides for the dashboard, the REST API and webhook integrations. The full technical
          documentation set ships with the repository (<code>docs/</code>).
        </p>
        <a href="/api/v1/docs/" className="btn btn-primary">
          Open interactive API reference ↗
        </a>
      </div>

      {SECTIONS.map((section) => (
        <section className="mb-5" id={section.title.toLowerCase().replace(/\s/g, "-")} key={section.title}>
          <h3 className="fw-bold mb-4">{section.title}</h3>
          <div className="row g-4">
            {section.items.map(([title, body]) => (
              <div className="col-md-4" key={title}>
                <div className="cs-card p-4 h-100">
                  <h6 className="fw-semibold">{title}</h6>
                  <p className="text-secondary small mb-0">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}

      <section className="mb-4" id="webhooks">
        <h3 className="fw-bold mb-3">Webhook verification example</h3>
        <pre className="code-block">
{`import hashlib, hmac

def verify(secret: str, timestamp: str, raw_body: bytes, signature_header: str) -> bool:
    # signature_header looks like: "t=1700000000,v1=8f3a…"
    v1 = dict(part.split("=", 1) for part in signature_header.split(","))["v1"]
    expected = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, v1)`}
        </pre>
        <p className="text-secondary small">
          Reject deliveries older than 5 minutes to defeat replays. Full details in{" "}
          <code>docs/WEBHOOKS.md</code>.
        </p>
      </section>

      <div className="text-center pt-2">
        <Link href="/register" className="btn btn-outline-secondary px-4">
          Try it with a free workspace
        </Link>
      </div>
    </div>
  );
}
