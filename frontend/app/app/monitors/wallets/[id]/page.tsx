"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import { ActiveBadge, SeverityBadge, StatusBadge } from "@/components/ui/Badges";
import EmptyState from "@/components/ui/EmptyState";
import { BlockSkeleton, TableSkeleton } from "@/components/ui/Skeletons";
import { confirmDialog, toast } from "@/lib/dialogs";
import { eventTypeLabel, formatAmount, formatDate, shortHash, timeAgo } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace-context";
import { walletMonitorService } from "@/services/monitors";
import type { BlockchainEvent, MonitorStats, WalletMonitor } from "@/types";

export default function WalletMonitorDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { current, canWrite } = useWorkspace();
  const [monitor, setMonitor] = useState<WalletMonitor | null>(null);
  const [stats, setStats] = useState<MonitorStats | null>(null);
  const [activity, setActivity] = useState<BlockchainEvent[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!current) return;
    const monitorId = Number(id);
    Promise.all([
      walletMonitorService.get(monitorId),
      walletMonitorService.stats(monitorId),
      walletMonitorService.activity(monitorId),
    ])
      .then(([m, s, a]) => {
        setMonitor(m);
        setStats(s);
        setActivity(a);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Not found"));
  }, [id, current]);

  if (error) return <div className="alert alert-danger">{error}</div>;
  if (!monitor) return <BlockSkeleton height={400} />;

  const toggle = async () => {
    const updated = monitor.is_active
      ? await walletMonitorService.pause(monitor.id)
      : await walletMonitorService.resume(monitor.id);
    setMonitor(updated);
  };

  const remove = async () => {
    const confirmed = await confirmDialog({
      title: `Delete “${monitor.name}”?`,
      text: "The monitor stops immediately. Events it already captured remain in the explorer.",
      confirmText: "Delete monitor",
      danger: true,
    });
    if (!confirmed) return;
    await walletMonitorService.remove(monitor.id);
    toast("Wallet monitor deleted");
    router.push("/app/monitors/wallets");
  };

  return (
    <>
      <PageHeader
        title={monitor.name}
        subtitle={`${monitor.address} · ${monitor.chain_name}`}
        actions={
          <>
            <ActiveBadge active={monitor.is_active} />
            {canWrite && (
              <>
                <button className="btn btn-outline-secondary btn-sm" onClick={() => void toggle()}>
                  {monitor.is_active ? "Pause" : "Resume"}
                </button>
                <Link href={`/app/monitors/wallets/${monitor.id}/edit`} className="btn btn-outline-secondary btn-sm">
                  Edit
                </Link>
                <button className="btn btn-outline-danger btn-sm" onClick={() => void remove()}>
                  Delete
                </button>
              </>
            )}
          </>
        }
      />

      {monitor.last_error && (
        <div className="alert alert-warning py-2 small">
          Last error ({monitor.error_count} total): {monitor.last_error}
        </div>
      )}

      <div className="row g-3 mb-3">
        {[
          ["Events total", stats?.total_events],
          ["Events 24h", stats?.events_24h],
          ["Events 7d", stats?.events_7d],
          ["Alerts", stats?.alerts_total],
          ["Last processed block", monitor.last_processed_block ? `#${monitor.last_processed_block.toLocaleString()}` : "—"],
          ["Confirmations", monitor.required_confirmations],
        ].map(([label, value]) => (
          <div className="col-6 col-lg-2" key={String(label)}>
            <div className="stat-card">
              <div className="stat-label">{label}</div>
              <div className="stat-value fs-5">{value === undefined ? "…" : String(value ?? "—")}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="row g-3">
        <div className="col-lg-4">
          <div className="cs-card p-3 h-100">
            <h6 className="fw-semibold mb-3">Configuration</h6>
            <dl className="row small mb-0">
              <dt className="col-6 text-secondary fw-normal">Direction</dt>
              <dd className="col-6 text-capitalize">{monitor.direction}</dd>
              <dt className="col-6 text-secondary fw-normal">Categories</dt>
              <dd className="col-6">{monitor.event_types.map(eventTypeLabel).join(", ")}</dd>
              <dt className="col-6 text-secondary fw-normal">Severity</dt>
              <dd className="col-6"><SeverityBadge severity={monitor.severity} /></dd>
              <dt className="col-6 text-secondary fw-normal">Token filter</dt>
              <dd className="col-6 mono">{monitor.token_contract || "any"}</dd>
              <dt className="col-6 text-secondary fw-normal">Min value (wei)</dt>
              <dd className="col-6 mono">{monitor.min_value_wei || "—"}</dd>
              <dt className="col-6 text-secondary fw-normal">Large threshold</dt>
              <dd className="col-6 mono">{monitor.large_tx_threshold_wei || "—"}</dd>
              <dt className="col-6 text-secondary fw-normal">Tags</dt>
              <dd className="col-6">{monitor.tags.join(", ") || "—"}</dd>
              <dt className="col-6 text-secondary fw-normal">Created</dt>
              <dd className="col-6">{formatDate(monitor.created_at)}</dd>
            </dl>
            {monitor.notes && (
              <>
                <hr style={{ borderColor: "var(--cs-border)" }} />
                <p className="small text-secondary mb-0">{monitor.notes}</p>
              </>
            )}
          </div>
        </div>

        <div className="col-lg-8">
          <div className="cs-card h-100">
            <div className="d-flex justify-content-between align-items-center p-3 pb-2">
              <h6 className="fw-semibold mb-0">Recent activity</h6>
              <span className="small text-secondary">last event {timeAgo(monitor.last_event_at)}</span>
            </div>
            {activity === null ? (
              <TableSkeleton />
            ) : activity.length === 0 ? (
              <EmptyState icon="⛓" title="No events captured yet" body="Events appear once the engine sees matching on-chain activity." />
            ) : (
              <div className="table-scroll">
                <table className="table table-cs">
                  <thead>
                    <tr><th>Type</th><th>Amount</th><th>Tx</th><th>Block</th><th>Status</th><th>When</th></tr>
                  </thead>
                  <tbody>
                    {activity.map((event) => (
                      <tr key={event.id}>
                        <td>
                          <Link href={`/app/events/${event.id}`} className="text-body fw-semibold">
                            {eventTypeLabel(event.event_type)}
                          </Link>
                        </td>
                        <td className="mono small">{formatAmount(event)}</td>
                        <td className="mono small">{shortHash(event.tx_hash)}</td>
                        <td className="mono small">{event.block_number.toLocaleString()}</td>
                        <td><StatusBadge status={event.status} /></td>
                        <td className="small text-secondary">{timeAgo(event.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
