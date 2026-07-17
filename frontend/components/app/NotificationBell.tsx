"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { notificationService } from "@/services/platform";
import type { Notification } from "@/types";
import { timeAgo } from "@/lib/format";
import { SeverityBadge } from "@/components/ui/Badges";

const POLL_MS = 30_000;

export default function NotificationBell() {
  const [unread, setUnread] = useState(0);
  const [items, setItems] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const { unread: count } = await notificationService.unreadCount();
      setUnread(count);
    } catch {
      /* signed out or offline — badge just stays stale */
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(refresh, POLL_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  const loadItems = async () => {
    try {
      const page = await notificationService.list({ page_size: 8 });
      setItems(page.results);
    } catch {
      setItems([]);
    }
  };

  return (
    <div className="position-relative">
      <button
        type="button"
        className="btn btn-outline-secondary btn-sm position-relative"
        aria-label={`Notifications (${unread} unread)`}
        onClick={async () => {
          const next = !open;
          setOpen(next);
          if (next) await loadItems();
        }}
      >
        🔔
        {unread > 0 && (
          <span className="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          className="cs-card position-absolute end-0 mt-2 shadow"
          style={{ width: 360, maxWidth: "88vw", zIndex: 1050 }}
        >
          <div className="d-flex justify-content-between align-items-center px-3 py-2 border-bottom" style={{ borderColor: "var(--cs-border)" }}>
            <strong className="small">Notifications</strong>
            <button
              className="btn btn-link btn-sm p-0 small"
              onClick={async () => {
                await notificationService.markAllRead();
                setUnread(0);
                await loadItems();
              }}
            >
              Mark all read
            </button>
          </div>
          <div style={{ maxHeight: 380, overflowY: "auto" }}>
            {items.length === 0 && (
              <div className="p-4 text-center small text-secondary">Nothing here yet.</div>
            )}
            {items.map((n) => (
              <Link
                key={n.id}
                href={n.link || "/app/notifications"}
                className={`d-block notification-item text-body ${n.read_at ? "" : "unread"}`}
                onClick={async () => {
                  setOpen(false);
                  if (!n.read_at) {
                    try {
                      await notificationService.markRead(n.id);
                      setUnread((u) => Math.max(0, u - 1));
                    } catch { /* ignore */ }
                  }
                }}
              >
                <div className="d-flex justify-content-between gap-2 align-items-start">
                  <span className="small fw-semibold">{n.title}</span>
                  <SeverityBadge severity={n.severity} />
                </div>
                <div className="small text-secondary mt-1">{timeAgo(n.created_at)}</div>
              </Link>
            ))}
          </div>
          <div className="px-3 py-2 border-top text-center" style={{ borderColor: "var(--cs-border)" }}>
            <Link href="/app/notifications" className="small" onClick={() => setOpen(false)}>
              View all notifications
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
