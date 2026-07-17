import type { Metadata } from "next";

export const metadata: Metadata = { title: "Terms of service" };

export default function TermsPage() {
  return (
    <div className="container py-5" style={{ maxWidth: 780 }}>
      <span className="section-eyebrow">Legal</span>
      <h1 className="fw-bold mt-2 mb-1">Terms of Service</h1>
      <p className="text-secondary small mb-5">Last updated: July 2026</p>

      <div className="d-grid gap-4 text-secondary">
        <section>
          <h5 className="text-body fw-semibold">1. The service</h5>
          <p className="mb-0">
            ChainSentinel provides read-only monitoring of public blockchain data: wallet
            activity, token transfers, approvals and smart-contract events, with alerting and
            webhook delivery. The service never holds keys and never executes transactions.
          </p>
        </section>
        <section>
          <h5 className="text-body fw-semibold">2. Accounts & workspaces</h5>
          <p className="mb-0">
            You are responsible for safeguarding your credentials and API keys, and for the
            actions of members you invite. Workspace owners control membership, webhooks, API
            keys and deletion.
          </p>
        </section>
        <section>
          <h5 className="text-body fw-semibold">3. Acceptable use</h5>
          <p className="mb-0">
            Don&apos;t use the platform to attack third parties (including webhook endpoints you
            don&apos;t control), to evade RPC provider terms, to probe internal networks, or to
            harass. Abusive workspaces may be suspended.
          </p>
        </section>
        <section>
          <h5 className="text-body fw-semibold">4. No financial advice, no guarantees of completeness</h5>
          <p className="mb-0">
            Blockchain networks reorganize, RPC providers fail, and delivery systems retry.
            ChainSentinel is engineered for reliability — idempotent ingestion, confirmation
            tracking, failover — but is provided “as is” without warranty that every event will
            be detected or delivered in time. It is a monitoring aid, not a custody control.
          </p>
        </section>
        <section>
          <h5 className="text-body fw-semibold">5. Fees</h5>
          <p className="mb-0">
            During early access the service is free. Future paid tiers will be announced in
            advance; continued use after a pricing change constitutes acceptance.
          </p>
        </section>
        <section>
          <h5 className="text-body fw-semibold">6. Termination</h5>
          <p className="mb-0">
            You may delete your workspace or account at any time. We may suspend accounts that
            violate these terms, with notice where practical.
          </p>
        </section>
        <section>
          <h5 className="text-body fw-semibold">7. Changes</h5>
          <p className="mb-0">
            We may update these terms; material changes will be communicated by email or an
            in-app notice before they take effect.
          </p>
        </section>
      </div>
    </div>
  );
}
