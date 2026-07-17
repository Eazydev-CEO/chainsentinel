"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import { ActiveBadge, SeverityBadge } from "@/components/ui/Badges";
import EmptyState from "@/components/ui/EmptyState";
import Pagination from "@/components/ui/Pagination";
import { TableSkeleton } from "@/components/ui/Skeletons";
import { shortAddress, timeAgo } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace-context";
import { contractMonitorService } from "@/services/monitors";
import type { ContractMonitor, Paginated } from "@/types";

export default function ContractMonitorsPage() {
  const { current, canWrite } = useWorkspace();
  const [data, setData] = useState<Paginated<ContractMonitor> | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");

  const load = useCallback(async () => {
    if (!current) return;
    setData(null);
    try {
      setData(await contractMonitorService.list({ page, search: appliedSearch || undefined }));
    } catch {
      setData({ count: 0, next: null, previous: null, results: [] });
    }
  }, [current, page, appliedSearch]);

  useEffect(() => {
    void load();
  }, [load]);

  const toggleActive = async (monitor: ContractMonitor) => {
    const updated = monitor.is_active
      ? await contractMonitorService.pause(monitor.id)
      : await contractMonitorService.resume(monitor.id);
    setData((d) =>
      d ? { ...d, results: d.results.map((m) => (m.id === updated.id ? updated : m)) } : d
    );
  };

  return (
    <>
      <PageHeader
        title="Contract monitors"
        subtitle="Decode and track custom events from any contract ABI."
        actions={
          canWrite ? (
            <Link href="/app/monitors/contracts/new" className="btn btn-primary btn-sm">
              + New monitor
            </Link>
          ) : undefined
        }
      />

      <form
        className="d-flex gap-2 mb-3"
        onSubmit={(e) => {
          e.preventDefault();
          setPage(1);
          setAppliedSearch(search);
        }}
      >
        <input
          className="form-control form-control-sm"
          style={{ maxWidth: 340 }}
          placeholder="Search name, address…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button className="btn btn-outline-secondary btn-sm">Search</button>
      </form>

      <div className="cs-card">
        {data === null ? (
          <TableSkeleton rows={8} cols={7} />
        ) : data.results.length === 0 ? (
          <EmptyState
            icon="📜"
            title="No contract monitors yet"
            body="Paste an ABI, pick the events, and decoded logs start flowing in."
            actionLabel={canWrite ? "Create contract monitor" : undefined}
            actionHref={canWrite ? "/app/monitors/contracts/new" : undefined}
          />
        ) : (
          <>
            <div className="table-scroll">
              <table className="table table-cs">
                <thead>
                  <tr>
                    <th>Name</th><th>Contract</th><th>Chain</th><th>Events</th>
                    <th>Severity</th><th>Status</th><th>Last event</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((monitor) => (
                    <tr key={monitor.id}>
                      <td>
                        <Link href={`/app/monitors/contracts/${monitor.id}`} className="fw-semibold text-body">
                          {monitor.name}
                        </Link>
                        {monitor.label && <div className="small text-secondary">{monitor.label}</div>}
                      </td>
                      <td><span className="address-chip">{shortAddress(monitor.address)}</span></td>
                      <td className="small">{monitor.chain_name}</td>
                      <td className="small">{monitor.selected_events.join(", ") || "—"}</td>
                      <td><SeverityBadge severity={monitor.severity} /></td>
                      <td><ActiveBadge active={monitor.is_active} /></td>
                      <td className="small text-secondary">{timeAgo(monitor.last_event_at)}</td>
                      <td className="text-end">
                        {canWrite && (
                          <div className="btn-group btn-group-sm">
                            <button className="btn btn-outline-secondary" onClick={() => void toggleActive(monitor)}>
                              {monitor.is_active ? "Pause" : "Resume"}
                            </button>
                            <Link href={`/app/monitors/contracts/${monitor.id}/edit`} className="btn btn-outline-secondary">
                              Edit
                            </Link>
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
