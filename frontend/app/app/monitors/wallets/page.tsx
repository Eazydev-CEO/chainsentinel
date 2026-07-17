"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import { ActiveBadge, SeverityBadge } from "@/components/ui/Badges";
import EmptyState from "@/components/ui/EmptyState";
import Pagination from "@/components/ui/Pagination";
import { TableSkeleton } from "@/components/ui/Skeletons";
import { shortAddress, timeAgo } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace-context";
import { walletMonitorService } from "@/services/monitors";
import type { CsvImportReport, Paginated, WalletMonitor } from "@/types";
import { ApiError } from "@/lib/api";

export default function WalletMonitorsPage() {
  const { current, canWrite } = useWorkspace();
  const [data, setData] = useState<Paginated<WalletMonitor> | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [importReport, setImportReport] = useState<CsvImportReport | null>(null);
  const [importError, setImportError] = useState("");
  const [importing, setImporting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    if (!current) return;
    setData(null);
    try {
      setData(await walletMonitorService.list({ page, search: appliedSearch || undefined }));
    } catch {
      setData({ count: 0, next: null, previous: null, results: [] });
    }
  }, [current, page, appliedSearch]);

  useEffect(() => {
    void load();
  }, [load]);

  const onImport = async (file: File) => {
    setImporting(true);
    setImportError("");
    setImportReport(null);
    try {
      const report = await walletMonitorService.importCsv(file);
      setImportReport(report);
      await load();
    } catch (err) {
      setImportError(err instanceof ApiError ? err.message : "Import failed.");
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const toggleActive = async (monitor: WalletMonitor) => {
    const updated = monitor.is_active
      ? await walletMonitorService.pause(monitor.id)
      : await walletMonitorService.resume(monitor.id);
    setData((d) =>
      d ? { ...d, results: d.results.map((m) => (m.id === updated.id ? updated : m)) } : d
    );
  };

  return (
    <>
      <PageHeader
        title="Wallet monitors"
        subtitle="Track native, token and NFT movement plus approval activity per address."
        actions={
          canWrite ? (
            <>
              <label className="btn btn-outline-secondary btn-sm mb-0">
                {importing ? "Importing…" : "⇪ Import CSV"}
                <input
                  ref={fileRef}
                  type="file"
                  accept=".csv"
                  hidden
                  disabled={importing}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) void onImport(file);
                  }}
                />
              </label>
              {current && (
                <a
                  className="btn btn-outline-secondary btn-sm"
                  href={walletMonitorService.exportCsvUrl(current.id)}
                >
                  ⇩ Export CSV
                </a>
              )}
              <Link href="/app/monitors/wallets/new" className="btn btn-primary btn-sm">
                + New monitor
              </Link>
            </>
          ) : undefined
        }
      />

      {importError && <div className="alert alert-danger py-2 small">{importError}</div>}
      {importReport && (
        <div className={`alert py-3 small ${importReport.failed_count ? "alert-warning" : "alert-success"}`}>
          <div className="d-flex justify-content-between flex-wrap gap-2">
            <strong>
              Import “{importReport.filename}”: {importReport.created_count} created,{" "}
              {importReport.failed_count} failed of {importReport.total_rows} rows.
            </strong>
            <button className="btn-close" aria-label="Dismiss" onClick={() => setImportReport(null)} />
          </div>
          {importReport.failed_count > 0 && (
            <ul className="mb-0 mt-2">
              {importReport.report.rows
                .filter((row) => row.status === "error")
                .slice(0, 8)
                .map((row) => (
                  <li key={row.row}>
                    Row {row.row} ({row.name || row.address}): {(row.errors || []).join("; ")}
                  </li>
                ))}
              {importReport.failed_count > 8 && <li>…and more (full report stored).</li>}
            </ul>
          )}
        </div>
      )}

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
          placeholder="Search name, address, notes…"
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
            icon="👛"
            title="No wallet monitors yet"
            body="Add an address to start capturing transfers and approvals — or import a CSV."
            actionLabel={canWrite ? "Create your first monitor" : undefined}
            actionHref={canWrite ? "/app/monitors/wallets/new" : undefined}
          />
        ) : (
          <>
            <div className="table-scroll">
              <table className="table table-cs">
                <thead>
                  <tr>
                    <th>Name</th><th>Address</th><th>Chain</th><th>Direction</th>
                    <th>Severity</th><th>Status</th><th>Last event</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((monitor) => (
                    <tr key={monitor.id}>
                      <td>
                        <Link href={`/app/monitors/wallets/${monitor.id}`} className="fw-semibold text-body">
                          {monitor.name}
                        </Link>
                        {monitor.tags.length > 0 && (
                          <div className="small text-secondary">{monitor.tags.join(" · ")}</div>
                        )}
                      </td>
                      <td><span className="address-chip">{shortAddress(monitor.address)}</span></td>
                      <td className="small">{monitor.chain_name}</td>
                      <td className="small text-capitalize">{monitor.direction}</td>
                      <td><SeverityBadge severity={monitor.severity} /></td>
                      <td>
                        <ActiveBadge active={monitor.is_active} />
                        {monitor.error_count > 0 && (
                          <span className="ms-1 badge-status st-failed">{monitor.error_count} errs</span>
                        )}
                      </td>
                      <td className="small text-secondary">{timeAgo(monitor.last_event_at)}</td>
                      <td className="text-end">
                        {canWrite && (
                          <div className="btn-group btn-group-sm">
                            <button className="btn btn-outline-secondary" onClick={() => void toggleActive(monitor)}>
                              {monitor.is_active ? "Pause" : "Resume"}
                            </button>
                            <Link href={`/app/monitors/wallets/${monitor.id}/edit`} className="btn btn-outline-secondary">
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

      <p className="form-hint mt-3">
        CSV header: <code>name,address,chain,direction,event_types,token_contract,min_value_wei,large_tx_threshold_wei,severity,tags,notes</code>{" "}
        — lists use <code>|</code> separators. Rows are validated individually; invalid rows are reported and skipped.
      </p>
    </>
  );
}
