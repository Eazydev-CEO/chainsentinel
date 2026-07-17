"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import { SeverityBadge, StatusBadge } from "@/components/ui/Badges";
import EmptyState from "@/components/ui/EmptyState";
import Pagination from "@/components/ui/Pagination";
import { TableSkeleton } from "@/components/ui/Skeletons";
import { timeAgo } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace-context";
import { alertService } from "@/services/platform";
import type { Alert, Paginated } from "@/types";

export default function AlertsPage() {
  const { current, role } = useWorkspace();
  const canAct = role === "owner" || role === "admin" || role === "analyst";
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Paginated<Alert> | null>(null);

  const load = useCallback(async () => {
    if (!current) return;
    setData(null);
    try {
      setData(
        await alertService.list({
          page,
          status: status || undefined,
          severity: severity || undefined,
        })
      );
    } catch {
      setData({ count: 0, next: null, previous: null, results: [] });
    }
  }, [current, page, status, severity]);

  useEffect(() => {
    void load();
  }, [load]);

  const act = async (alert: Alert, action: "acknowledge" | "resolve") => {
    const updated =
      action === "acknowledge"
        ? await alertService.acknowledge(alert.id)
        : await alertService.resolve(alert.id);
    setData((d) =>
      d ? { ...d, results: d.results.map((a) => (a.id === updated.id ? updated : a)) } : d
    );
  };

  return (
    <>
      <PageHeader
        title="Alerts"
        subtitle="Everything your rules decided was worth waking someone up for."
        actions={<Link href="/app/alert-rules" className="btn btn-outline-secondary btn-sm">Manage rules</Link>}
      />

      <div className="d-flex gap-2 mb-3 flex-wrap">
        <select className="form-select form-select-sm" style={{ width: 170 }} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} aria-label="Status filter">
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="resolved">Resolved</option>
        </select>
        <select className="form-select form-select-sm" style={{ width: 170 }} value={severity} onChange={(e) => { setSeverity(e.target.value); setPage(1); }} aria-label="Severity filter">
          <option value="">All severities</option>
          {["critical", "high", "medium", "low", "info"].map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      <div className="cs-card">
        {data === null ? (
          <TableSkeleton rows={8} cols={6} />
        ) : data.results.length === 0 ? (
          <EmptyState
            icon="🔔"
            title="No alerts match"
            body="Quiet is good. Create alert rules to be notified when it isn't."
            actionLabel="Create alert rule"
            actionHref="/app/alert-rules/new"
          />
        ) : (
          <>
            <div className="table-scroll">
              <table className="table table-cs">
                <thead>
                  <tr>
                    <th>Alert</th><th>Severity</th><th>Status</th><th>Rule</th>
                    <th>Occurrences</th><th>Last seen</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((alert) => (
                    <tr key={alert.id}>
                      <td style={{ maxWidth: 380 }}>
                        <Link href={`/app/alerts/${alert.id}`} className="fw-semibold text-body">
                          {alert.title}
                        </Link>
                      </td>
                      <td><SeverityBadge severity={alert.severity} /></td>
                      <td><StatusBadge status={alert.status} /></td>
                      <td className="small">{alert.rule_name || "—"}</td>
                      <td className="small">{alert.count > 1 ? `×${alert.count} (grouped)` : "1"}</td>
                      <td className="small text-secondary">{timeAgo(alert.last_seen_at)}</td>
                      <td className="text-end">
                        {canAct && alert.status !== "resolved" && (
                          <div className="btn-group btn-group-sm">
                            {alert.status === "open" && (
                              <button className="btn btn-outline-secondary" onClick={() => void act(alert, "acknowledge")}>
                                Ack
                              </button>
                            )}
                            <button className="btn btn-outline-secondary" onClick={() => void act(alert, "resolve")}>
                              Resolve
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination count={data.count} page={page} onPage={setPage} />
          </>
        )}
      </div>
    </>
  );
}
