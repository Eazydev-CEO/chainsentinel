"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import { SeverityBadge, StatusBadge } from "@/components/ui/Badges";
import CopyButton from "@/components/ui/CopyButton";
import { BlockSkeleton } from "@/components/ui/Skeletons";
import { eventTypeLabel, formatAmount, formatDate } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace-context";
import { eventService } from "@/services/platform";
import type { BlockchainEventDetail } from "@/types";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="row py-2 border-bottom mx-0" style={{ borderColor: "var(--cs-border)" }}>
      <div className="col-sm-4 col-lg-3 text-secondary small">{label}</div>
      <div className="col-sm-8 col-lg-9 small" style={{ wordBreak: "break-all" }}>{children}</div>
    </div>
  );
}

export default function EventDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { current } = useWorkspace();
  const [event, setEvent] = useState<BlockchainEventDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!current) return;
    eventService
      .get(Number(id))
      .then(setEvent)
      .catch((err) => setError(err instanceof Error ? err.message : "Not found"));
  }, [id, current]);

  if (error) return <div className="alert alert-danger">{error}</div>;
  if (!event) return <BlockSkeleton height={420} />;

  const monitorHref = event.wallet_monitor_id
    ? `/app/monitors/wallets/${event.wallet_monitor_id}`
    : event.contract_monitor_id
      ? `/app/monitors/contracts/${event.contract_monitor_id}`
      : null;

  return (
    <>
      <PageHeader
        title={eventTypeLabel(event.event_type)}
        subtitle={`Event #${event.id} on ${event.chain_name}`}
        actions={
          <>
            <StatusBadge status={event.status} />
            <SeverityBadge severity={event.severity} />
            {event.is_large && <span className="badge-severity severity-high">large</span>}
          </>
        }
      />

      <div className="row g-3">
        <div className="col-lg-8">
          <div className="cs-card p-3 mb-3">
            <h6 className="fw-semibold mb-2">Transaction</h6>
            <Row label="Tx hash">
              <span className="mono">{event.tx_hash}</span>{" "}
              <CopyButton value={event.tx_hash} label="Copy" />
              {event.explorer_tx_url && (
                <a href={event.explorer_tx_url} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-outline-secondary ms-1">
                  Explorer ↗
                </a>
              )}
            </Row>
            <Row label="Block">
              <span className="mono">#{event.block_number.toLocaleString()}</span>
              <span className="text-secondary ms-2">hash {event.block_hash}</span>
            </Row>
            <Row label="Position">
              tx index {event.tx_index ?? "—"} · log index {event.log_index ?? "— (native)"}
            </Row>
            <Row label="Occurred">{formatDate(event.occurred_at)} (block time)</Row>
            <Row label="Confirmations">
              {event.current_confirmations ?? "—"} of {event.confirmations_required} required
              {event.confirmed_at && <span className="text-secondary ms-2">confirmed {formatDate(event.confirmed_at)}</span>}
            </Row>
          </div>

          <div className="cs-card p-3 mb-3">
            <h6 className="fw-semibold mb-2">Participants & value</h6>
            {event.from_address && <Row label="From"><span className="mono">{event.from_address}</span></Row>}
            {event.to_address && <Row label="To"><span className="mono">{event.to_address}</span></Row>}
            {event.spender_address && <Row label="Spender / operator"><span className="mono">{event.spender_address}</span></Row>}
            {event.contract_address && <Row label="Contract"><span className="mono">{event.contract_address}</span></Row>}
            {event.token_address && (
              <Row label="Token">
                <span className="mono">{event.token_address}</span>
                {event.token_symbol && <span className="ms-2">({event.token_symbol}{event.token_decimals !== null ? `, ${event.token_decimals} decimals` : ""})</span>}
              </Row>
            )}
            {event.token_id && <Row label="Token ID">{event.token_id}</Row>}
            <Row label="Amount">
              <strong>{formatAmount(event)}</strong>
              {event.amount_wei && <span className="text-secondary ms-2 mono">raw {event.amount_wei}</span>}
            </Row>
          </div>

          {(event.decoded || event.decode_error) && (
            <div className="cs-card p-3 mb-3">
              <h6 className="fw-semibold mb-2">Decoded event</h6>
              {event.event_signature && (
                <Row label="Signature"><span className="mono">{event.event_signature}</span></Row>
              )}
              {event.topic0 && <Row label="Topic0"><span className="mono">{event.topic0}</span></Row>}
              {event.decode_error && (
                <div className="alert alert-warning small mt-2 mb-2">
                  Decoding failed: {event.decode_error}. Raw log preserved below.
                </div>
              )}
              {event.decoded && (
                <pre className="code-block mt-2 mb-0">{JSON.stringify(event.decoded, null, 2)}</pre>
              )}
            </div>
          )}

          {event.raw && (
            <div className="cs-card p-3">
              <h6 className="fw-semibold mb-2">Raw payload</h6>
              <pre className="code-block mb-0">{JSON.stringify(event.raw, null, 2)}</pre>
            </div>
          )}
        </div>

        <div className="col-lg-4 d-grid gap-3 align-content-start">
          <div className="cs-card p-3">
            <h6 className="fw-semibold mb-2">Context</h6>
            <Row label="Chain">{event.chain_name}</Row>
            <Row label="Monitor">
              {monitorHref ? (
                <Link href={monitorHref}>{event.monitor_name}</Link>
              ) : (
                event.monitor_name || "—"
              )}
              <span className="text-secondary ms-1">({event.monitor_kind})</span>
            </Row>
            <Row label="Detected">{formatDate(event.created_at)}</Row>
            {event.reverted_at && <Row label="Reverted">{formatDate(event.reverted_at)} (reorg)</Row>}
          </div>

          <div className="cs-card p-3">
            <h6 className="fw-semibold mb-2">Related alerts</h6>
            {event.related_alerts.length === 0 ? (
              <p className="small text-secondary mb-0">No alerts fired for this event.</p>
            ) : (
              <ul className="list-unstyled mb-0 d-grid gap-2">
                {event.related_alerts.map((alert) => (
                  <li key={alert.id} className="d-flex justify-content-between align-items-center gap-2">
                    <Link href={`/app/alerts/${alert.id}`} className="small">{alert.title}</Link>
                    <SeverityBadge severity={alert.severity} />
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="cs-card p-3">
            <h6 className="fw-semibold mb-3">Timeline</h6>
            <div>
              {event.timeline.map((entry, index) => (
                <div className="workflow-step" data-step={index + 1} key={index}>
                  <strong className="small">{entry.label}</strong>
                  <div className="small text-secondary">{entry.detail}</div>
                  <div className="small text-secondary">{formatDate(entry.at)}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
