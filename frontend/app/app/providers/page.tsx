"use client";

import { useEffect, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import { HealthDot, StatusBadge } from "@/components/ui/Badges";
import EmptyState from "@/components/ui/EmptyState";
import { TableSkeleton } from "@/components/ui/Skeletons";
import { timeAgo } from "@/lib/format";
import { chainService } from "@/services/platform";
import type { ProviderHealth } from "@/types";

export default function ProvidersPage() {
  const [providers, setProviders] = useState<ProviderHealth[] | null>(null);

  const load = () =>
    chainService.providerHealth().then(setProviders).catch(() => setProviders([]));

  useEffect(() => {
    void load();
    const timer = setInterval(load, 30_000);
    return () => clearInterval(timer);
  }, []);

  return (
    <>
      <PageHeader
        title="RPC provider health"
        subtitle="Live status of the endpoints powering ingestion. Endpoint URLs stay server-side."
      />

      <div className="cs-card">
        {providers === null ? (
          <TableSkeleton rows={6} cols={7} />
        ) : providers.length === 0 ? (
          <EmptyState
            icon="🖧"
            title="No RPC providers configured"
            body="Set RPC_*_HTTP env vars and run the seed command, or add providers in Django admin."
          />
        ) : (
          <div className="table-scroll">
            <table className="table table-cs">
              <thead>
                <tr>
                  <th>Chain</th><th>Provider</th><th>Priority</th><th>Health</th>
                  <th>Latency</th><th>Failures</th><th>Last success</th><th>Last failure reason</th>
                </tr>
              </thead>
              <tbody>
                {providers.map((provider) => (
                  <tr key={provider.id}>
                    <td className="small">{provider.chain_name}</td>
                    <td className="small fw-semibold">
                      <HealthDot status={provider.health_status} />
                      {provider.name}
                      {!provider.is_active && <span className="ms-2 badge-status st-paused">disabled</span>}
                    </td>
                    <td className="small">{provider.priority}</td>
                    <td><StatusBadge status={provider.health_status} /></td>
                    <td className="small">{provider.last_latency_ms !== null ? `${provider.last_latency_ms}ms` : "—"}</td>
                    <td className="small">{provider.consecutive_failures}</td>
                    <td className="small text-secondary">{timeAgo(provider.last_success_at)}</td>
                    <td className="small text-secondary" style={{ maxWidth: 240 }}>
                      {provider.last_failure_reason || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <p className="form-hint mt-3">
        Health is probed every minute by the worker. Failing providers back off exponentially and
        recover automatically; chains keep polling through the next healthy provider by priority.
      </p>
    </>
  );
}
