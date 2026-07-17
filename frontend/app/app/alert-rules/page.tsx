"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import { ActiveBadge, SeverityBadge } from "@/components/ui/Badges";
import EmptyState from "@/components/ui/EmptyState";
import Pagination from "@/components/ui/Pagination";
import { TableSkeleton } from "@/components/ui/Skeletons";
import { confirmDialog, toast } from "@/lib/dialogs";
import { eventTypeLabel, timeAgo } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace-context";
import { alertRuleService } from "@/services/platform";
import type { AlertRule, Paginated } from "@/types";

export default function AlertRulesPage() {
  const { current, canWrite } = useWorkspace();
  const [data, setData] = useState<Paginated<AlertRule> | null>(null);
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    if (!current) return;
    setData(null);
    try {
      setData(await alertRuleService.list({ page }));
    } catch {
      setData({ count: 0, next: null, previous: null, results: [] });
    }
  }, [current, page]);

  useEffect(() => {
    void load();
  }, [load]);

  const toggle = async (rule: AlertRule) => {
    const updated = await alertRuleService.update(rule.id, { is_active: !rule.is_active });
    setData((d) => (d ? { ...d, results: d.results.map((r) => (r.id === updated.id ? updated : r)) } : d));
  };

  const remove = async (rule: AlertRule) => {
    const confirmed = await confirmDialog({
      title: `Delete rule “${rule.name}”?`,
      text: "It stops evaluating immediately. Alerts it already raised are kept.",
      confirmText: "Delete rule",
      danger: true,
    });
    if (!confirmed) return;
    await alertRuleService.remove(rule.id);
    toast("Alert rule deleted");
    await load();
  };

  return (
    <>
      <PageHeader
        title="Alert rules"
        subtitle="Conditions that turn raw events into actionable alerts."
        actions={canWrite ? <Link href="/app/alert-rules/new" className="btn btn-primary btn-sm">+ New rule</Link> : undefined}
      />

      <div className="cs-card">
        {data === null ? (
          <TableSkeleton rows={6} cols={6} />
        ) : data.results.length === 0 ? (
          <EmptyState
            icon="⚙"
            title="No alert rules yet"
            body="Without rules, events are only visible in the explorer. Add a rule to get notified."
            actionLabel={canWrite ? "Create your first rule" : undefined}
            actionHref={canWrite ? "/app/alert-rules/new" : undefined}
          />
        ) : (
          <>
            <div className="table-scroll">
              <table className="table table-cs">
                <thead>
                  <tr>
                    <th>Rule</th><th>Filters</th><th>Actions</th><th>Severity</th>
                    <th>Status</th><th>Last triggered</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((rule) => (
                    <tr key={rule.id}>
                      <td>
                        <span className="fw-semibold">{rule.name}</span>
                        {rule.description && <div className="small text-secondary">{rule.description}</div>}
                      </td>
                      <td className="small text-secondary" style={{ maxWidth: 260 }}>
                        {[
                          rule.wallet_monitor_name && `monitor: ${rule.wallet_monitor_name}`,
                          rule.contract_monitor_name && `contract: ${rule.contract_monitor_name}`,
                          rule.chain && `chain: ${rule.chain}`,
                          rule.event_types.length > 0 && rule.event_types.map(eventTypeLabel).join(", "),
                          rule.min_amount_wei && `min ${rule.min_amount_wei} wei`,
                        ]
                          .filter(Boolean)
                          .join(" · ") || "matches everything"}
                      </td>
                      <td className="small">
                        {[
                          rule.notify_in_app && "in-app",
                          rule.notify_email && "email",
                          rule.notify_webhook && "webhook",
                        ]
                          .filter(Boolean)
                          .join(", ") || "—"}
                      </td>
                      <td>{rule.severity ? <SeverityBadge severity={rule.severity} /> : <span className="small text-secondary">inherit</span>}</td>
                      <td><ActiveBadge active={rule.is_active} /></td>
                      <td className="small text-secondary">{timeAgo(rule.last_triggered_at)}</td>
                      <td className="text-end">
                        {canWrite && (
                          <div className="btn-group btn-group-sm">
                            <button className="btn btn-outline-secondary" onClick={() => void toggle(rule)}>
                              {rule.is_active ? "Disable" : "Enable"}
                            </button>
                            <Link href={`/app/alert-rules/${rule.id}/edit`} className="btn btn-outline-secondary">Edit</Link>
                            <button className="btn btn-outline-danger" onClick={() => void remove(rule)}>Delete</button>
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
