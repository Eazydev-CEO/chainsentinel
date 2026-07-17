"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import { SeverityBadge } from "@/components/ui/Badges";
import EmptyState from "@/components/ui/EmptyState";
import Pagination from "@/components/ui/Pagination";
import { TableSkeleton } from "@/components/ui/Skeletons";
import { timeAgo } from "@/lib/format";
import { notificationService } from "@/services/platform";
import type { Notification, NotificationPrefs, Paginated, Severity } from "@/types";

const SEVERITIES: Severity[] = ["info", "low", "medium", "high", "critical"];

export default function NotificationsPage() {
  const [data, setData] = useState<Paginated<Notification> | null>(null);
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [prefs, setPrefs] = useState<NotificationPrefs | null>(null);
  const [savedFlash, setSavedFlash] = useState(false);

  const load = useCallback(async () => {
    setData(null);
    try {
      setData(await notificationService.list({ page, unread: unreadOnly ? "true" : undefined }));
    } catch {
      setData({ count: 0, next: null, previous: null, results: [] });
    }
  }, [page, unreadOnly]);

  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    notificationService.preferences().then(setPrefs).catch(() => setPrefs(null));
  }, []);

  const savePrefs = async (patch: Partial<NotificationPrefs>) => {
    if (!prefs) return;
    const updated = await notificationService.updatePreferences({ ...prefs, ...patch });
    setPrefs(updated);
    setSavedFlash(true);
    setTimeout(() => setSavedFlash(false), 1500);
  };

  const markRead = async (notification: Notification) => {
    if (notification.read_at) return;
    const updated = await notificationService.markRead(notification.id);
    setData((d) => (d ? { ...d, results: d.results.map((n) => (n.id === updated.id ? updated : n)) } : d));
  };

  return (
    <>
      <PageHeader
        title="Notifications"
        subtitle="In-app notices across all your workspaces."
        actions={
          <>
            <label className="form-check form-switch small mb-0 d-flex align-items-center gap-2">
              <input
                className="form-check-input"
                type="checkbox"
                checked={unreadOnly}
                onChange={(e) => {
                  setUnreadOnly(e.target.checked);
                  setPage(1);
                }}
              />
              Unread only
            </label>
            <button
              className="btn btn-outline-secondary btn-sm"
              onClick={async () => {
                await notificationService.markAllRead();
                await load();
              }}
            >
              Mark all read
            </button>
          </>
        }
      />

      <div className="row g-3">
        <div className="col-lg-8">
          <div className="cs-card">
            {data === null ? (
              <TableSkeleton rows={8} cols={3} />
            ) : data.results.length === 0 ? (
              <EmptyState icon="✉" title="No notifications" body="Alert and system notices land here." />
            ) : (
              <>
                <ul className="list-unstyled mb-0">
                  {data.results.map((notification) => (
                    <li
                      key={notification.id}
                      className={`notification-item ${notification.read_at ? "" : "unread"}`}
                    >
                      <div className="d-flex justify-content-between gap-2 align-items-start">
                        <Link
                          href={notification.link || "#"}
                          className="fw-semibold small text-body"
                          onClick={() => void markRead(notification)}
                        >
                          {notification.title}
                        </Link>
                        <SeverityBadge severity={notification.severity} />
                      </div>
                      {notification.body && (
                        <div className="small text-secondary mt-1" style={{ whiteSpace: "pre-line" }}>
                          {notification.body.length > 220
                            ? `${notification.body.slice(0, 220)}…`
                            : notification.body}
                        </div>
                      )}
                      <div className="form-hint mt-1">
                        {notification.workspace_name && <span className="me-2">{notification.workspace_name}</span>}
                        {timeAgo(notification.created_at)}
                        {!notification.read_at && (
                          <button className="btn btn-link btn-sm p-0 ms-2 small" onClick={() => void markRead(notification)}>
                            mark read
                          </button>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
                <Pagination count={data.count} page={page} onPage={setPage} />
              </>
            )}
          </div>
        </div>

        <div className="col-lg-4">
          <div className="cs-card p-3">
            <div className="d-flex justify-content-between align-items-center mb-3">
              <h6 className="fw-semibold mb-0">Preferences</h6>
              {savedFlash && <span className="small text-success">Saved ✓</span>}
            </div>
            {!prefs ? (
              <TableSkeleton rows={4} cols={2} />
            ) : (
              <div className="d-grid gap-3">
                <div>
                  <label className="form-label small">Minimum in-app severity</label>
                  <select
                    className="form-select form-select-sm"
                    value={prefs.min_severity_in_app}
                    onChange={(e) => void savePrefs({ min_severity_in_app: e.target.value as Severity })}
                  >
                    {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label className="form-label small">Minimum email severity</label>
                  <select
                    className="form-select form-select-sm"
                    value={prefs.min_severity_email}
                    onChange={(e) => void savePrefs({ min_severity_email: e.target.value as Severity })}
                  >
                    {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                {(
                  [
                    ["email_critical_alerts", "Email me critical alerts"],
                    ["email_failed_webhooks", "Email me failed webhooks"],
                    ["email_provider_outage", "Email me provider outages"],
                    ["email_daily_summary", "Send me the daily summary"],
                  ] as const
                ).map(([key, label]) => (
                  <label className="form-check form-switch small" key={key}>
                    <input
                      className="form-check-input"
                      type="checkbox"
                      checked={prefs[key]}
                      onChange={(e) => void savePrefs({ [key]: e.target.checked })}
                    />
                    <span className="form-check-label">{label}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
