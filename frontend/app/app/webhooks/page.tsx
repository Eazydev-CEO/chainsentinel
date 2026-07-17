"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import { StatusBadge } from "@/components/ui/Badges";
import EmptyState from "@/components/ui/EmptyState";
import { TableSkeleton } from "@/components/ui/Skeletons";
import { timeAgo } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace-context";
import { webhookService } from "@/services/platform";
import type { WebhookEndpoint } from "@/types";

export default function WebhooksPage() {
  const { current, canWrite } = useWorkspace();
  const [endpoints, setEndpoints] = useState<WebhookEndpoint[] | null>(null);
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    if (!current) return;
    setEndpoints(null);
    try {
      const page = await webhookService.list({ page_size: 100 });
      setEndpoints(page.results);
    } catch {
      setEndpoints([]);
    }
  }, [current]);

  useEffect(() => {
    void load();
  }, [load]);

  const test = async (endpoint: WebhookEndpoint) => {
    await webhookService.test(endpoint.id);
    setNotice(`Test ping queued for “${endpoint.name}” — watch the deliveries list.`);
  };

  const toggle = async (endpoint: WebhookEndpoint) => {
    const updated = await webhookService.update(endpoint.id, { enabled: !endpoint.enabled });
    setEndpoints((all) => all?.map((e) => (e.id === updated.id ? updated : e)) ?? null);
  };

  return (
    <>
      <PageHeader
        title="Webhooks"
        subtitle="HMAC-signed deliveries with retries, logs and replay."
        actions={canWrite ? <Link href="/app/webhooks/new" className="btn btn-primary btn-sm">+ New endpoint</Link> : undefined}
      />

      {notice && (
        <div className="alert alert-info py-2 small d-flex justify-content-between">
          {notice}
          <button className="btn-close" aria-label="Dismiss" onClick={() => setNotice("")} />
        </div>
      )}

      <div className="cs-card">
        {endpoints === null ? (
          <TableSkeleton rows={5} cols={6} />
        ) : endpoints.length === 0 ? (
          <EmptyState
            icon="⇄"
            title="No webhook endpoints"
            body="Send alerts and confirmed events to your own systems — signed and retried."
            actionLabel={canWrite ? "Add an endpoint" : undefined}
            actionHref={canWrite ? "/app/webhooks/new" : undefined}
          />
        ) : (
          <div className="table-scroll">
            <table className="table table-cs">
              <thead>
                <tr>
                  <th>Endpoint</th><th>Events</th><th>Status</th><th>Last delivery</th>
                  <th>Last success</th><th></th>
                </tr>
              </thead>
              <tbody>
                {endpoints.map((endpoint) => (
                  <tr key={endpoint.id}>
                    <td>
                      <Link href={`/app/webhooks/${endpoint.id}`} className="fw-semibold text-body">
                        {endpoint.name}
                      </Link>
                      <div className="small text-secondary text-truncate" style={{ maxWidth: 300 }}>
                        {endpoint.url}
                      </div>
                    </td>
                    <td className="small">{endpoint.event_types.join(", ")}</td>
                    <td>
                      <StatusBadge status={endpoint.enabled ? "active" : "paused"} />
                      {endpoint.last_status === "failed" && (
                        <span className="ms-1 badge-status st-failed">failing</span>
                      )}
                    </td>
                    <td className="small text-secondary">
                      {endpoint.last_status
                        ? `${endpoint.last_status}${endpoint.last_failure_reason ? ` (${endpoint.last_failure_reason})` : ""}`
                        : "never"}
                    </td>
                    <td className="small text-secondary">{timeAgo(endpoint.last_success_at)}</td>
                    <td className="text-end">
                      {canWrite && (
                        <div className="btn-group btn-group-sm">
                          <button className="btn btn-outline-secondary" onClick={() => void test(endpoint)}>
                            Send test
                          </button>
                          <button className="btn btn-outline-secondary" onClick={() => void toggle(endpoint)}>
                            {endpoint.enabled ? "Disable" : "Enable"}
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
