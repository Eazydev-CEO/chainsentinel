"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import { StatusBadge } from "@/components/ui/Badges";
import CopyButton from "@/components/ui/CopyButton";
import EmptyState from "@/components/ui/EmptyState";
import Pagination from "@/components/ui/Pagination";
import { BlockSkeleton, TableSkeleton } from "@/components/ui/Skeletons";
import { confirmDialog, toast } from "@/lib/dialogs";
import { formatDate, timeAgo } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace-context";
import { webhookService } from "@/services/platform";
import type { Paginated, WebhookDelivery, WebhookEndpoint } from "@/types";

export default function WebhookDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { current, canWrite } = useWorkspace();
  const [endpoint, setEndpoint] = useState<WebhookEndpoint | null>(null);
  const [deliveries, setDeliveries] = useState<Paginated<WebhookDelivery> | null>(null);
  const [page, setPage] = useState(1);
  const [freshSecret, setFreshSecret] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);

  const load = useCallback(async () => {
    if (!current) return;
    try {
      setEndpoint(await webhookService.get(Number(id)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Not found");
    }
  }, [id, current]);

  const loadDeliveries = useCallback(async () => {
    if (!current) return;
    setDeliveries(null);
    try {
      setDeliveries(await webhookService.deliveries({ endpoint: id, page }));
    } catch {
      setDeliveries({ count: 0, next: null, previous: null, results: [] });
    }
  }, [id, current, page]);

  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    void loadDeliveries();
  }, [loadDeliveries]);

  if (error) return <div className="alert alert-danger">{error}</div>;
  if (!endpoint) return <BlockSkeleton height={380} />;

  const regenerate = async () => {
    const confirmed = await confirmDialog({
      title: "Regenerate signing secret?",
      text: "The current secret stops validating immediately — update your receiver right after.",
      confirmText: "Regenerate",
      danger: true,
    });
    if (!confirmed) return;
    const updated = await webhookService.regenerateSecret(endpoint.id);
    setFreshSecret(updated.secret || "");
    toast("New secret generated — copy it now");
  };

  const test = async () => {
    await webhookService.test(endpoint.id);
    setNotice("Test ping queued — it will appear in the deliveries below shortly.");
    setTimeout(() => void loadDeliveries(), 1500);
  };

  const replay = async (delivery: WebhookDelivery) => {
    await webhookService.replay(delivery.id);
    setNotice(`Replay of delivery #${delivery.id} queued.`);
    await loadDeliveries();
  };

  const remove = async () => {
    const confirmed = await confirmDialog({
      title: `Delete “${endpoint.name}”?`,
      text: "The endpoint and its entire delivery history are removed permanently.",
      confirmText: "Delete endpoint",
      danger: true,
    });
    if (!confirmed) return;
    await webhookService.remove(endpoint.id);
    toast("Webhook endpoint deleted");
    router.push("/app/webhooks");
  };

  return (
    <>
      <PageHeader
        title={endpoint.name}
        subtitle={endpoint.url}
        actions={
          <>
            <StatusBadge status={endpoint.enabled ? "active" : "paused"} />
            {canWrite && (
              <>
                <button className="btn btn-outline-secondary btn-sm" onClick={() => void test()}>Send test</button>
                <button className="btn btn-outline-secondary btn-sm" onClick={() => void regenerate()}>Regenerate secret</button>
                <button
                  className="btn btn-outline-secondary btn-sm"
                  onClick={async () => {
                    const updated = await webhookService.update(endpoint.id, { enabled: !endpoint.enabled });
                    setEndpoint(updated);
                  }}
                >
                  {endpoint.enabled ? "Disable" : "Enable"}
                </button>
                <button className="btn btn-outline-danger btn-sm" onClick={() => void remove()}>Delete</button>
              </>
            )}
          </>
        }
      />

      {notice && (
        <div className="alert alert-info py-2 small d-flex justify-content-between">
          {notice}
          <button className="btn-close" aria-label="Dismiss" onClick={() => setNotice("")} />
        </div>
      )}

      {freshSecret && (
        <div className="alert alert-warning small">
          <strong>New signing secret — copy it now, it will not be shown again:</strong>
          <div className="d-flex gap-2 mt-2">
            <input className="form-control form-control-sm mono" readOnly value={freshSecret} />
            <CopyButton value={freshSecret} />
          </div>
        </div>
      )}

      <div className="row g-3 mb-3">
        <div className="col-md-3 col-6">
          <div className="stat-card">
            <div className="stat-label">Subscribed events</div>
            <div className="small mt-1">{endpoint.event_types.map((t) => <code key={t} className="me-1">{t}</code>)}</div>
          </div>
        </div>
        <div className="col-md-3 col-6">
          <div className="stat-card">
            <div className="stat-label">Retry limit</div>
            <div className="stat-value fs-5">{endpoint.max_retries}</div>
            <div className="stat-sub">timeout {endpoint.timeout_seconds}s</div>
          </div>
        </div>
        <div className="col-md-3 col-6">
          <div className="stat-card">
            <div className="stat-label">Last status</div>
            <div className="stat-value fs-5">{endpoint.last_status || "—"}</div>
            <div className="stat-sub">{endpoint.last_failure_reason || ""}</div>
          </div>
        </div>
        <div className="col-md-3 col-6">
          <div className="stat-card">
            <div className="stat-label">Last success</div>
            <div className="stat-value fs-6">{timeAgo(endpoint.last_success_at)}</div>
          </div>
        </div>
      </div>

      <div className="cs-card">
        <div className="p-3 pb-2 d-flex justify-content-between align-items-center">
          <h6 className="fw-semibold mb-0">Delivery history</h6>
          <span className="small text-secondary">every attempt is recorded</span>
        </div>
        {deliveries === null ? (
          <TableSkeleton rows={6} cols={6} />
        ) : deliveries.results.length === 0 ? (
          <EmptyState icon="⇄" title="No deliveries yet" body="Send a test ping to verify connectivity and signatures." />
        ) : (
          <>
            <div className="table-scroll">
              <table className="table table-cs">
                <thead>
                  <tr>
                    <th>Event</th><th>Status</th><th>Attempts</th><th>Response</th>
                    <th>Latency</th><th>Next retry</th><th>Created</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {deliveries.results.map((delivery) => (
                    <>
                      <tr key={delivery.id}>
                        <td className="small"><code>{delivery.event_type}</code>{delivery.replay_of && <span className="ms-1 text-secondary">(replay)</span>}</td>
                        <td><StatusBadge status={delivery.status} /></td>
                        <td className="small">{delivery.attempt_count}/{delivery.max_attempts}</td>
                        <td className="small">{delivery.response_status ?? delivery.failure_reason ?? "—"}</td>
                        <td className="small">{delivery.response_time_ms !== null ? `${delivery.response_time_ms}ms` : "—"}</td>
                        <td className="small text-secondary">{delivery.next_retry_at ? formatDate(delivery.next_retry_at) : "—"}</td>
                        <td className="small text-secondary">{timeAgo(delivery.created_at)}</td>
                        <td className="text-end">
                          <div className="btn-group btn-group-sm">
                            <button
                              className="btn btn-outline-secondary"
                              onClick={() => setExpanded(expanded === delivery.id ? null : delivery.id)}
                            >
                              {expanded === delivery.id ? "Hide" : "Payload"}
                            </button>
                            {canWrite && (
                              <button className="btn btn-outline-secondary" onClick={() => void replay(delivery)}>
                                Replay
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                      {expanded === delivery.id && (
                        <tr key={`${delivery.id}-payload`}>
                          <td colSpan={8}>
                            <pre className="code-block mb-0">{JSON.stringify(delivery.payload, null, 2)}</pre>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination count={deliveries.count} page={page} onPage={setPage} />
          </>
        )}
      </div>
    </>
  );
}
