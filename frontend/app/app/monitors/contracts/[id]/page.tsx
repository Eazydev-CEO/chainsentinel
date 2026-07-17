"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import { ActiveBadge, SeverityBadge, StatusBadge } from "@/components/ui/Badges";
import EmptyState from "@/components/ui/EmptyState";
import { BlockSkeleton, TableSkeleton } from "@/components/ui/Skeletons";
import { confirmDialog, toast } from "@/lib/dialogs";
import { formatDate, shortHash, timeAgo } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace-context";
import { contractMonitorService } from "@/services/monitors";
import type { BlockchainEvent, ContractMonitor, MonitorStats } from "@/types";

export default function ContractMonitorDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { current, canWrite } = useWorkspace();
  const [monitor, setMonitor] = useState<ContractMonitor | null>(null);
  const [stats, setStats] = useState<MonitorStats | null>(null);
  const [activity, setActivity] = useState<BlockchainEvent[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!current) return;
    const monitorId = Number(id);
    Promise.all([
      contractMonitorService.get(monitorId),
      contractMonitorService.stats(monitorId),
      contractMonitorService.activity(monitorId),
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
      ? await contractMonitorService.pause(monitor.id)
      : await contractMonitorService.resume(monitor.id);
    setMonitor(updated);
  };

  const remove = async () => {
    const confirmed = await confirmDialog({
      title: `Delete “${monitor.name}”?`,
      text: "Event subscriptions are removed; captured events remain in the explorer.",
      confirmText: "Delete monitor",
      danger: true,
    });
    if (!confirmed) return;
    await contractMonitorService.remove(monitor.id);
    toast("Contract monitor deleted");
    router.push("/app/monitors/contracts");
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
                <Link href={`/app/monitors/contracts/${monitor.id}/edit`} className="btn btn-outline-secondary btn-sm">
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
          <div className="cs-card p-3 mb-3">
            <h6 className="fw-semibold mb-3">Subscribed events</h6>
            {monitor.available_events
              .filter((event) => monitor.selected_events.includes(event.name))
              .map((event) => (
                <div key={event.signature} className="mb-3">
                  <div className="fw-semibold small">{event.name}</div>
                  <div className="mono form-hint">{event.signature}</div>
                  <div className="mono form-hint text-truncate">topic0: {event.topic0}</div>
                  {monitor.topic_filters[event.name] && (
                    <div className="small text-secondary mt-1">
                      Filters:{" "}
                      {Object.entries(monitor.topic_filters[event.name])
                        .map(([param, value]) => `${param}=${value}`)
                        .join(", ")}
                    </div>
                  )}
                </div>
              ))}
            <hr style={{ borderColor: "var(--cs-border)" }} />
            <dl className="row small mb-0">
              <dt className="col-6 text-secondary fw-normal">ABI document</dt>
              <dd className="col-6">{monitor.abi_document?.name || "—"}</dd>
              <dt className="col-6 text-secondary fw-normal">Severity</dt>
              <dd className="col-6"><SeverityBadge severity={monitor.severity} /></dd>
              <dt className="col-6 text-secondary fw-normal">Tags</dt>
              <dd className="col-6">{monitor.tags.join(", ") || "—"}</dd>
              <dt className="col-6 text-secondary fw-normal">Created</dt>
              <dd className="col-6">{formatDate(monitor.created_at)}</dd>
            </dl>
          </div>
        </div>

        <div className="col-lg-8">
          <div className="cs-card h-100">
            <div className="d-flex justify-content-between align-items-center p-3 pb-2">
              <h6 className="fw-semibold mb-0">Recent decoded events</h6>
              <span className="small text-secondary">last event {timeAgo(monitor.last_event_at)}</span>
            </div>
            {activity === null ? (
              <TableSkeleton />
            ) : activity.length === 0 ? (
              <EmptyState icon="📜" title="No contract events captured yet" />
            ) : (
              <div className="table-scroll">
                <table className="table table-cs">
                  <thead>
                    <tr><th>Event</th><th>Tx</th><th>Block</th><th>Status</th><th>When</th></tr>
                  </thead>
                  <tbody>
                    {activity.map((event) => (
                      <tr key={event.id}>
                        <td>
                          <Link href={`/app/events/${event.id}`} className="text-body fw-semibold small">
                            {event.monitor_kind === "contract" ? "Contract event" : event.event_type}
                          </Link>
                        </td>
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
