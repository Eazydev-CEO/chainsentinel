"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import { SeverityBadge, StatusBadge } from "@/components/ui/Badges";
import { BlockSkeleton } from "@/components/ui/Skeletons";
import { formatDate } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace-context";
import { alertService } from "@/services/platform";
import type { AlertDetail } from "@/types";

export default function AlertDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { current, role } = useWorkspace();
  const canAct = role === "owner" || role === "admin" || role === "analyst";
  const [alert, setAlert] = useState<AlertDetail | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!current) return;
    try {
      setAlert(await alertService.get(Number(id)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Not found");
    }
  }, [id, current]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) return <div className="alert alert-danger">{error}</div>;
  if (!alert) return <BlockSkeleton height={400} />;

  const act = async (action: "acknowledge" | "resolve") => {
    setBusy(true);
    try {
      if (action === "acknowledge") await alertService.acknowledge(alert.id);
      else await alertService.resolve(alert.id);
      await load();
    } finally {
      setBusy(false);
    }
  };

  const submitNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!note.trim()) return;
    setBusy(true);
    try {
      await alertService.addNote(alert.id, note.trim());
      setNote("");
      await load();
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader
        title={alert.title}
        subtitle={`Alert #${alert.id}${alert.rule_name ? ` · rule: ${alert.rule_name}` : ""}`}
        actions={
          <>
            <SeverityBadge severity={alert.severity} />
            <StatusBadge status={alert.status} />
            {canAct && alert.status === "open" && (
              <button className="btn btn-outline-secondary btn-sm" disabled={busy} onClick={() => void act("acknowledge")}>
                Acknowledge
              </button>
            )}
            {canAct && alert.status !== "resolved" && (
              <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => void act("resolve")}>
                Resolve
              </button>
            )}
          </>
        }
      />

      <div className="row g-3">
        <div className="col-lg-7">
          <div className="cs-card p-3 mb-3">
            <h6 className="fw-semibold mb-2">Details</h6>
            <pre className="code-block mb-3" style={{ whiteSpace: "pre-wrap" }}>{alert.message}</pre>
            <dl className="row small mb-0">
              <dt className="col-5 col-md-3 text-secondary fw-normal">Occurrences</dt>
              <dd className="col-7 col-md-9">{alert.count > 1 ? `${alert.count} (grouped within the rule's window)` : "1"}</dd>
              <dt className="col-5 col-md-3 text-secondary fw-normal">First seen</dt>
              <dd className="col-7 col-md-9">{formatDate(alert.first_seen_at)}</dd>
              <dt className="col-5 col-md-3 text-secondary fw-normal">Last seen</dt>
              <dd className="col-7 col-md-9">{formatDate(alert.last_seen_at)}</dd>
              {alert.event_id && (
                <>
                  <dt className="col-5 col-md-3 text-secondary fw-normal">Source event</dt>
                  <dd className="col-7 col-md-9">
                    <Link href={`/app/events/${alert.event_id}`}>View blockchain event #{alert.event_id} →</Link>
                  </dd>
                </>
              )}
              {alert.acknowledged_at && (
                <>
                  <dt className="col-5 col-md-3 text-secondary fw-normal">Acknowledged</dt>
                  <dd className="col-7 col-md-9">{formatDate(alert.acknowledged_at)} by {alert.acknowledged_by_email || "—"}</dd>
                </>
              )}
              {alert.resolved_at && (
                <>
                  <dt className="col-5 col-md-3 text-secondary fw-normal">Resolved</dt>
                  <dd className="col-7 col-md-9">{formatDate(alert.resolved_at)} by {alert.resolved_by_email || "—"}</dd>
                </>
              )}
            </dl>
          </div>

          <div className="cs-card p-3">
            <h6 className="fw-semibold mb-3">Internal notes</h6>
            {alert.notes.length === 0 && <p className="small text-secondary">No notes yet.</p>}
            <ul className="list-unstyled d-grid gap-2 mb-3">
              {alert.notes.map((n) => (
                <li key={n.id} className="cs-card p-2 px-3" style={{ background: "var(--cs-bg-raised)" }}>
                  <div className="small">{n.body}</div>
                  <div className="form-hint mt-1">{n.author_email || "unknown"} · {formatDate(n.created_at)}</div>
                </li>
              ))}
            </ul>
            {canAct && (
              <form onSubmit={submitNote} className="d-flex gap-2">
                <input
                  className="form-control form-control-sm"
                  placeholder="Add an investigation note…"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  maxLength={2000}
                />
                <button className="btn btn-outline-secondary btn-sm" disabled={busy || !note.trim()}>
                  Add
                </button>
              </form>
            )}
          </div>
        </div>

        <div className="col-lg-5">
          <div className="cs-card p-3">
            <h6 className="fw-semibold mb-3">Timeline</h6>
            <div>
              {alert.timeline.map((entry, index) => (
                <div className="workflow-step" data-step={index + 1} key={index}>
                  <strong className="small">{entry.label}</strong>
                  <div className="small text-secondary">{entry.detail}</div>
                  <div className="form-hint">{formatDate(entry.at)}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
