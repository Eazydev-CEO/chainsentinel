"use client";

import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import ChartCanvas from "@/components/ui/ChartCanvas";
import EmptyState from "@/components/ui/EmptyState";
import { BlockSkeleton } from "@/components/ui/Skeletons";
import { shortAddress } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace-context";
import { analyticsService } from "@/services/platform";
import type { AnalyticsCharts } from "@/types";

const PALETTE = ["#4f8cff", "#37c2ce", "#2fbf71", "#ffb84f", "#ff5d5d", "#9b7aff", "#e879b9"];

export default function AnalyticsPage() {
  const { current } = useWorkspace();
  const [days, setDays] = useState(14);
  const [charts, setCharts] = useState<AnalyticsCharts | null>(null);

  useEffect(() => {
    if (!current) return;
    let cancelled = false;
    setCharts(null);
    analyticsService
      .charts(days)
      .then((data) => !cancelled && setCharts(data))
      .catch(() => !cancelled && setCharts(null));
    return () => {
      cancelled = true;
    };
  }, [current, days]);

  const byChain = useMemo(() => {
    if (!charts) return null;
    const dates = [...new Set(charts.events_by_chain.map((r) => r.date))].sort();
    const chains = [...new Set(charts.events_by_chain.map((r) => r.chain__slug))];
    return {
      type: "bar" as const,
      data: {
        labels: dates.map((d) => d.slice(5)),
        datasets: chains.map((chain, i) => ({
          label: chain,
          data: dates.map(
            (date) =>
              charts.events_by_chain.find((r) => r.date === date && r.chain__slug === chain)
                ?.count || 0
          ),
          backgroundColor: PALETTE[i % PALETTE.length],
          stack: "events",
        })),
      },
      options: {
        maintainAspectRatio: false,
        scales: { x: { stacked: true }, y: { stacked: true } },
      },
    };
  }, [charts]);

  const overTime = useMemo(() => {
    if (!charts) return null;
    return {
      type: "line" as const,
      data: {
        labels: charts.events_over_time.map((r) => r.date.slice(5)),
        datasets: [
          {
            label: "Detected",
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
            tension: 0.35,
          },
        ],
      },
      options: { maintainAspectRatio: false },
    };
  }, [charts]);

  const severity = useMemo(() => {
    if (!charts) return null;
    const colors: Record<string, string> = {
      info: "#5b7ea8", low: "#37c2ce", medium: "#4f8cff", high: "#ffb84f", critical: "#ff5d5d",
    };
    return {
      type: "bar" as const,
      data: {
        labels: charts.alerts_by_severity.map((r) => r.severity),
        datasets: [
          {
            label: "Alerts",
            data: charts.alerts_by_severity.map((r) => r.count),
            backgroundColor: charts.alerts_by_severity.map((r) => colors[r.severity] || "#56627a"),
          },
        ],
      },
      options: { maintainAspectRatio: false, indexAxis: "y" as const, plugins: { legend: { display: false } } },
    };
  }, [charts]);

  const webhookTrend = useMemo(() => {
    if (!charts) return null;
    return {
      type: "bar" as const,
      data: {
        labels: charts.webhook_trend.map((r) => r.date.slice(5)),
        datasets: [
          { label: "Delivered", data: charts.webhook_trend.map((r) => r.ok), backgroundColor: "#2fbf71", stack: "wh" },
          { label: "Failed", data: charts.webhook_trend.map((r) => r.failed), backgroundColor: "#ff5d5d", stack: "wh" },
        ],
      },
      options: {
        maintainAspectRatio: false,
        scales: { x: { stacked: true }, y: { stacked: true } },
      },
    };
  }, [charts]);

  return (
    <>
      <PageHeader
        title="Analytics"
        subtitle="Every number below is computed from your workspace's real records."
        actions={
          <select
            className="form-select form-select-sm"
            style={{ width: 140 }}
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            aria-label="Time window"
          >
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        }
      />

      <div className="row g-3">
        <div className="col-lg-8">
          <div className="cs-card p-3">
            <h6 className="fw-semibold mb-3">Events by chain</h6>
            {byChain ? <ChartCanvas config={byChain} height={280} /> : <BlockSkeleton height={280} />}
          </div>
        </div>
        <div className="col-lg-4">
          <div className="cs-card p-3">
            <h6 className="fw-semibold mb-3">Alerts by severity</h6>
            {severity ? (
              charts!.alerts_by_severity.length ? (
                <ChartCanvas config={severity} height={280} />
              ) : (
                <EmptyState icon="🔕" title="No alerts in window" />
              )
            ) : (
              <BlockSkeleton height={280} />
            )}
          </div>
        </div>
        <div className="col-lg-7">
          <div className="cs-card p-3">
            <h6 className="fw-semibold mb-3">Events over time</h6>
            {overTime ? <ChartCanvas config={overTime} height={260} /> : <BlockSkeleton height={260} />}
          </div>
        </div>
        <div className="col-lg-5">
          <div className="cs-card p-3">
            <h6 className="fw-semibold mb-3">Webhook delivery trend</h6>
            {webhookTrend ? (
              charts!.webhook_trend.length ? (
                <ChartCanvas config={webhookTrend} height={260} />
              ) : (
                <EmptyState icon="⇄" title="No deliveries in window" />
              )
            ) : (
              <BlockSkeleton height={260} />
            )}
          </div>
        </div>

        <div className="col-lg-6">
          <div className="cs-card p-3">
            <h6 className="fw-semibold mb-3">Top monitored wallets</h6>
            {!charts ? (
              <BlockSkeleton height={200} />
            ) : charts.top_wallets.length === 0 ? (
              <EmptyState icon="👛" title="No wallet events in window" />
            ) : (
              <div className="table-scroll">
                <table className="table table-cs">
                  <thead><tr><th>Monitor</th><th>Address</th><th className="text-end">Events</th></tr></thead>
                  <tbody>
                    {charts.top_wallets.map((row) => (
                      <tr key={row.wallet_monitor__address + row.wallet_monitor__name}>
                        <td>{row.wallet_monitor__name}</td>
                        <td><span className="address-chip">{shortAddress(row.wallet_monitor__address)}</span></td>
                        <td className="text-end">{row.count.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
        <div className="col-lg-6">
          <div className="cs-card p-3">
            <h6 className="fw-semibold mb-3">Top contract events</h6>
            {!charts ? (
              <BlockSkeleton height={200} />
            ) : charts.top_contract_events.length === 0 ? (
              <EmptyState icon="📜" title="No contract events in window" />
            ) : (
              <div className="table-scroll">
                <table className="table table-cs">
                  <thead><tr><th>Monitor</th><th>Event</th><th className="text-end">Count</th></tr></thead>
                  <tbody>
                    {charts.top_contract_events.map((row, i) => (
                      <tr key={i}>
                        <td>{row.contract_monitor__name}</td>
                        <td className="mono small">{row.event_signature || "—"}</td>
                        <td className="text-end">{row.count.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
