"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import { TableSkeleton } from "@/components/ui/Skeletons";
import { promptDialog, toast } from "@/lib/dialogs";
import { formatDate } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace-context";
import { workspaceService } from "@/services/workspaces";
import type { AuditLog, Paginated } from "@/types";
import Pagination from "@/components/ui/Pagination";

export default function WorkspaceSettingsPage() {
  const { current, isOwner, role, reloadWorkspaces } = useWorkspace();
  const router = useRouter();
  const [name, setName] = useState(current?.name || "");
  const [saved, setSaved] = useState(false);
  const [audit, setAudit] = useState<Paginated<AuditLog> | null>(null);
  const [auditPage, setAuditPage] = useState(1);
  const canSeeAudit = role === "owner" || role === "admin";

  useEffect(() => {
    setName(current?.name || "");
  }, [current]);

  useEffect(() => {
    if (!current || !canSeeAudit) return;
    setAudit(null);
    workspaceService
      .auditLogs(auditPage)
      .then(setAudit)
      .catch(() => setAudit({ count: 0, next: null, previous: null, results: [] }));
  }, [current, auditPage, canSeeAudit]);

  if (!current) return null;

  const rename = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    await workspaceService.update(current.id, name.trim());
    await reloadWorkspaces();
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  const destroy = async () => {
    const typed = await promptDialog({
      title: "Delete this workspace?",
      text: `“${current.name}” and ALL of its monitors, events, alerts, webhooks and API keys are permanently deleted. Type the workspace name to confirm.`,
      placeholder: current.name,
      confirmText: "Delete forever",
      danger: true,
      validate: (value) =>
        value === current.name ? undefined : "Type the exact workspace name to confirm.",
    });
    if (typed === null) return;
    await workspaceService.remove(current.id);
    toast("Workspace deleted", "info");
    await reloadWorkspaces();
    router.push("/app");
  };

  return (
    <div style={{ maxWidth: 860 }}>
      <PageHeader title="Workspace settings" subtitle={`${current.name} · plan: ${current.plan}`} />

      <div className="cs-card p-4 mb-4">
        <h6 className="fw-semibold mb-3">General</h6>
        <form className="row g-2" onSubmit={rename}>
          <div className="col-md-6">
            <label className="form-label">Workspace name</label>
            <input className="form-control" value={name} onChange={(e) => setName(e.target.value)} disabled={!isOwner} maxLength={100} />
          </div>
          <div className="col-md-6 d-flex align-items-end gap-2">
            {isOwner && <button className="btn btn-primary">Rename</button>}
            {saved && <span className="text-success small align-self-center">Saved ✓</span>}
          </div>
        </form>
        <dl className="row small mt-3 mb-0 text-secondary">
          <dt className="col-4 col-md-2 fw-normal">Created</dt>
          <dd className="col-8 col-md-10">{formatDate(current.created_at)}</dd>
          <dt className="col-4 col-md-2 fw-normal">Your role</dt>
          <dd className="col-8 col-md-10 text-capitalize">{role}</dd>
          <dt className="col-4 col-md-2 fw-normal">Billing</dt>
          <dd className="col-8 col-md-10">Free early access — paid plans coming later (placeholder).</dd>
        </dl>
      </div>

      {canSeeAudit && (
        <div className="cs-card mb-4">
          <div className="p-3 pb-2">
            <h6 className="fw-semibold mb-0">Audit log</h6>
            <span className="form-hint">Security-relevant actions in this workspace.</span>
          </div>
          {audit === null ? (
            <TableSkeleton rows={5} cols={4} />
          ) : (
            <>
              <div className="table-scroll">
                <table className="table table-cs">
                  <thead>
                    <tr><th>When</th><th>Action</th><th>Actor</th><th>Target</th><th>IP</th></tr>
                  </thead>
                  <tbody>
                    {audit.results.map((entry) => (
                      <tr key={entry.id}>
                        <td className="small text-secondary">{formatDate(entry.created_at)}</td>
                        <td className="small"><code>{entry.action}</code></td>
                        <td className="small">{entry.actor_label || "system"}</td>
                        <td className="small text-secondary">{entry.target_label || "—"}</td>
                        <td className="small text-secondary">{entry.ip_address || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination count={audit.count} page={auditPage} onPage={setAuditPage} />
            </>
          )}
        </div>
      )}

      {isOwner && (
        <div className="cs-card p-4" style={{ borderColor: "rgba(255,93,93,.4)" }}>
          <h6 className="fw-semibold text-danger mb-2">Danger zone</h6>
          <p className="small text-secondary">
            Deleting the workspace removes all monitors, events, alerts, webhooks and API keys.
            This cannot be undone.
          </p>
          <button className="btn btn-outline-danger btn-sm" onClick={() => void destroy()}>
            Delete workspace
          </button>
        </div>
      )}
    </div>
  );
}
