"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import { SeverityBadge, StatusBadge, HealthDot } from "@/components/ui/Badges";
import ChartCanvas from "@/components/ui/ChartCanvas";
import EmptyState from "@/components/ui/EmptyState";
import { CardsSkeleton, TableSkeleton } from "@/components/ui/Skeletons";
import { formatAmount, eventTypeLabel, shortHash, timeAgo } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace-context";
import {
  alertService,
  analyticsService,
  chainService,
  eventService,
  webhookService,
} from "@/services/platform";
import type {
  Alert,
  AnalyticsCharts,
  AnalyticsOverview,
  BlockchainEvent,
  ProviderHealth,
  WebhookDelivery,
} from "@/types";

export default function DashboardPage() {
  const { current } = useWorkspace();
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [charts, setCharts] = useState<AnalyticsCharts | null>(null);
  const [events, setEvents] = useState<BlockchainEvent[] | null>(null);
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [failedDeliveries, setFailedDeliveries] = useState<WebhookDelivery[] | null>(null);
  const [providers, setProviders] = useState<ProviderHealth[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!current) return;
    let cancelled = false;
    setOverview(null);
    setEvents(null);
    (async () => {
      try {
        const [ov, ch, ev, al, wd, ph] = await Promise.all([
          analyticsService.overview(),
          analyticsService.charts(14),
          eventService.list({ page_size: 8 }),
          alertService.list({ page_size: 6, status: "open" }),
          webhookService.deliveries({ page_size: 5, status: "exhausted" }),
          chainService.providerHealth(),
        ]);
        if (cancelled) return;
        setOverview(ov);
        setCharts(ch);
        setEvents(ev.results);
        setAlerts(al.results);
        setFailedDeliveries(wd.results);
        setProviders(ph);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load dashboard");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [current]);

  const eventsChart = useMemo(() => {
    if (!charts) return null;
    return {
      type: "line" as const,
      data: {
        labels: charts.events_over_time.map((r) => r.date.slice(5)),
        datasets: [
          {
            label: "Events",
            data: charts.events_over_time.map((r) => r.count),
            borderColor: "#4f8cff",
            backgroundColor: "rgba(79,140,255,0.12)",
            fill: true,
            tension: 0.35,
          },
          {
            label: "Confirmed",
            data: charts.events_over_time.map((r) => r.confirmed),
            borderColor: "#2fbf71",
            backgroundColor: "transparent",
            tension: 0.35,
          },
        ],
      },
      options: { maintainAspectRatio: false, plugins: { legend: { display: true } } },
    };
  }, [charts]);

  const severityChart = useMemo(() => {
    if (!charts) return null;
    const colors: Record<string, string> = {
      info: "#5b7ea8", low: "#37c2ce", medium: "#4f8cff", high: "#ffb84f", critical: "#ff5d5d",
    };
    return {
      type: "doughnut" as const,
      data: {
        labels: charts.alerts_by_severity.map((r) => r.severity),
        datasets: [
          {
            data: charts.alerts_by_severity.map((r) => r.count),
            backgroundColor: charts.alerts_by_severity.map((r) => colors[r.severity] || "#56627a"),
            borderWidth: 0,
          },
        ],
      },
      options: { maintainAspectRatio: false, cutout: "62%" },
    };
  }, [charts]);

  if (error) {
    return <div className="alert alert-danger">{error}</div>;
  }

  const cards = overview
    ? [
        { label: "Active monitors", value: overview.active_monitors, sub: `${overview.total_monitors} total` },
        { label: "Events today", value: overview.events_today, sub: `${overview.events_24h} in 24h` },
        { label: "Critical alerts", value: overview.critical_alerts_open, sub: `${overview.open_alerts} open total` },
        {
          label: "Webhook success (24h)",
          value: overview.webhook_success_rate_24h === null ? "—" : `${overview.webhook_success_rate_24h}%`,
          sub: `${overview.webhook_deliveries_24h} deliveries`,
        },
        {
          label: "RPC providers",
          value: `${overview.providers_healthy}/${overview.providers_total}`,
          sub: "healthy / configured",
        },
        { label: "Transactions monitored", value: overview.transactions_monitored, sub: "all time" },
      ]
    : [];

  return (
    <>
      <PageHeader
        title="Overview"
        subtitle={current ? `Workspace: ${current.name}` : undefined}
        actions={
          <>
            <Link href="/app/monitors/wallets/new" className="btn btn-primary btn-sm">+ Wallet monitor</Link>
            <Link href="/app/alert-rules/new" className="btn btn-outline-secondary btn-sm">+ Alert rule</Link>
          </>
        }
      />

      {!overview ? (
        <CardsSkeleton count={6} />
      ) : (
        <div className="row g-3">
          {cards.map((card) => (
            <div className="col-6 col-lg-4 col-xl-2" key={card.label}>
              <div className="stat-card">
                <div className="stat-label">{card.label}</div>
                <div className="stat-value">{typeof card.value === "number" ? card.value.toLocaleString() : card.value}</div>
                <div className="stat-sub">{card.sub}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="row g-3 mt-1">
        <div className="col-lg-8">
          <div className="cs-card p-3 h-100">
            <h6 className="fw-semibold mb-3">Events over time (14d)</h6>
            {eventsChart ? <ChartCanvas config={eventsChart} height={250} /> : <TableSkeleton rows={4} />}
          </div>
        </div>
        <div className="col-lg-4">
          <div className="cs-card p-3 h-100">
            <h6 className="fw-semibold mb-3">Open alerts by severity (14d)</h6>
            {severityChart ? (
              charts!.alerts_by_severity.length ? (
                <ChartCanvas config={severityChart} height={250} />
              ) : (
                <EmptyState icon="🔕" title="No alerts in this window" />
              )
            ) : (
              <TableSkeleton rows={4} />
            )}
          </div>
        </div>
      </div>

      <div className="row g-3 mt-1">
        <div className="col-lg-7">
          <div className="cs-card">
            <div className="d-flex justify-content-between align-items-center p-3 pb-2">
              <h6 className="fw-semibold mb-0">Latest events</h6>
              <Link href="/app/events" className="small">Explore all →</Link>
            </div>
            {events === null ? (
              <TableSkeleton />
            ) : events.length === 0 ? (
              <EmptyState
                icon="⛓"
                title="No events yet"
                body="Create a monitor and events will stream in as blocks confirm."
                actionLabel="Create wallet monitor"
                actionHref="/app/monitors/wallets/new"
              />
            ) : (
              <div className="table-scroll">
                <table className="table table-cs">
                  <thead>
                    <tr><th>Type</th><th>Amount</th><th>Chain</th><th>Tx</th><th>Status</th><th>When</th></tr>
                  </thead>
                  <tbody>
                    {events.map((event) => (
                      <tr key={event.id}>
                        <td>
                          <Link href={`/app/events/${event.id}`} className="fw-semibold text-body">
                            {eventTypeLabel(event.event_type)}
                          </Link>
                          {event.is_large && <span className="ms-2 badge-severity severity-high">large</span>}
                        </td>
                        <td className="mono">{formatAmount(event)}</td>
                        <td>{event.chain_name}</td>
                        <td className="mono">{shortHash(event.tx_hash)}</td>
                        <td><StatusBadge status={event.status} /></td>
                        <td className="text-secondary small">{timeAgo(event.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        <div className="col-lg-5 d-grid gap-3 align-content-start">
          <div className="cs-card">
            <div className="d-flex justify-content-between align-items-center p-3 pb-2">
              <h6 className="fw-semibold mb-0">Open alerts</h6>
              <Link href="/app/alerts" className="small">All alerts →</Link>
            </div>
            {alerts === null ? (
              <TableSkeleton rows={3} />
            ) : alerts.length === 0 ? (
              <EmptyState icon="✓" title="Nothing needs attention" />
            ) : (
              <ul className="list-unstyled mb-0">
                {alerts.map((alert) => (
                  <li key={alert.id} className="notification-item">
                    <div className="d-flex justify-content-between gap-2">
                      <Link href={`/app/alerts/${alert.id}`} className="small fw-semibold text-body">
                        {alert.title}
                      </Link>
                      <SeverityBadge severity={alert.severity} />
                    </div>
                    <div className="small text-secondary mt-1">
                      {alert.count > 1 && <span className="me-2">×{alert.count}</span>}
                      {timeAgo(alert.last_seen_at)}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="cs-card">
            <div className="d-flex justify-content-between align-items-center p-3 pb-2">
              <h6 className="fw-semibold mb-0">RPC provider health</h6>
              <Link href="/app/providers" className="small">Details →</Link>
            </div>
            {providers === null ? (
              <TableSkeleton rows={3} />
            ) : providers.length === 0 ? (
              <EmptyState icon="🖧" title="No providers configured" body="Add RPC endpoints via env vars + seed, or in Django admin." />
            ) : (
              <ul className="list-unstyled mb-0">
                {providers.slice(0, 6).map((provider) => (
                  <li key={provider.id} className="notification-item d-flex justify-content-between align-items-center">
                    <span className="small">
                      <HealthDot status={provider.health_status} />
                      {provider.chain_name} · {provider.name}
                    </span>
                    <span className="small text-secondary">
                      {provider.last_latency_ms !== null ? `${provider.last_latency_ms}ms` : "—"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="cs-card">
            <div className="d-flex justify-content-between align-items-center p-3 pb-2">
              <h6 className="fw-semibold mb-0">Failed webhooks</h6>
              <Link href="/app/webhooks" className="small">Manage →</Link>
            </div>
            {failedDeliveries === null ? (
              <TableSkeleton rows={2} />
            ) : failedDeliveries.length === 0 ? (
              <EmptyState icon="✓" title="No exhausted deliveries" />
            ) : (
              <ul className="list-unstyled mb-0">
                {failedDeliveries.map((delivery) => (
                  <li key={delivery.id} className="notification-item small">
                    <div className="d-flex justify-content-between">
                      <span className="fw-semibold">{delivery.endpoint_name}</span>
                      <StatusBadge status={delivery.status} />
                    </div>
                    <div className="text-secondary mt-1">
                      {delivery.event_type} · {delivery.failure_reason || "failed"}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
