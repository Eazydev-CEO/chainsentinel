import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Pricing" };

const TIERS = [
  {
    name: "Free",
    price: "$0",
    tagline: "For personal wallets and evaluation",
    features: ["1 workspace", "5 active monitors", "2 webhook endpoints", "7-day event history", "Community support"],
    cta: "Start free",
    highlight: false,
  },
  {
    name: "Pro",
    price: "$49",
    tagline: "For teams running real treasuries",
    features: ["Unlimited workspaces", "100 active monitors", "Unlimited webhooks", "90-day event history", "API keys & CSV import", "Priority email support"],
    cta: "Start free — upgrade later",
    highlight: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    tagline: "For funds, custodians and infra teams",
    features: ["Custom monitor volume", "Dedicated RPC pools", "Long-term retention", "SSO (planned)", "Self-hosted deployments", "Support SLA"],
    cta: "Talk to us",
    highlight: false,
  },
];

export default function PricingPage() {
  return (
    <div className="container py-5">
      <div className="text-center mb-5">
        <span className="section-eyebrow">Pricing</span>
        <h1 className="fw-bold mt-2">Simple plans, honest limits</h1>
        <p className="text-secondary">
          <strong>Early access:</strong> billing is not enabled yet — every workspace currently
          runs with Pro-level limits, free. These tiers show where pricing is headed.
        </p>
      </div>

      <div className="row g-4 justify-content-center mb-5">
        {TIERS.map((tier) => (
          <div className="col-md-6 col-lg-4" key={tier.name}>
            <div
              className={`cs-card p-4 h-100 d-flex flex-column ${tier.highlight ? "border-primary" : ""}`}
              style={tier.highlight ? { borderColor: "var(--cs-accent)", boxShadow: "0 0 32px rgba(79,140,255,.12)" } : undefined}
            >
              {tier.highlight && (
                <span className="badge bg-primary align-self-start mb-2">Most popular</span>
              )}
              <h5 className="fw-semibold">{tier.name}</h5>
              <div className="display-6 fw-bold">
                {tier.price}
                {tier.price.startsWith("$") && tier.price !== "$0" && (
                  <span className="fs-6 text-secondary fw-normal"> /month</span>
                )}
              </div>
              <p className="text-secondary small">{tier.tagline}</p>
              <ul className="list-unstyled small d-grid gap-2 text-secondary flex-grow-1">
                {tier.features.map((feature) => (
                  <li key={feature}>✓ {feature}</li>
                ))}
              </ul>
              <Link
                href={tier.name === "Enterprise" ? "/contact" : "/register"}
                className={`btn mt-3 ${tier.highlight ? "btn-primary" : "btn-outline-secondary"}`}
              >
                {tier.cta}
              </Link>
            </div>
          </div>
        ))}
      </div>

      <p className="text-center text-secondary small">
        Questions about limits or self-hosting? <Link href="/contact">Contact us</Link>.
      </p>
    </div>
  );
}
