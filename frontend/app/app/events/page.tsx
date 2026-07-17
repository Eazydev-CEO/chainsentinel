"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import { SeverityBadge, StatusBadge } from "@/components/ui/Badges";
import EmptyState from "@/components/ui/EmptyState";
import Pagination from "@/components/ui/Pagination";
import { TableSkeleton } from "@/components/ui/Skeletons";
import { eventTypeLabel, formatAmount, shortAddress, shortHash, timeAgo } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace-context";
import { chainService, eventService } from "@/services/platform";
import type { BlockchainEvent, Chain, Paginated } from "@/types";

const EVENT_TYPES = [
  "native_received", "native_sent", "erc20_received", "erc20_sent", "nft_received",
  "nft_sent", "approval_created", "approval_changed", "approval_revoked",
  "approval_for_all", "contract_event",
];
const STATUSES = ["pending", "confirmed", "reverted", "failed", "ignored"];
const SEVERITIES = ["info", "low", "medium", "high", "critical"];

interface Filters {
  chain: string;
  event_type: string;
  status: string;
  severity: string;
  address: string;
  tx_hash: string;
  block_number: string;
  token: string;
  date_from: string;
  date_to: string;
  is_large: string;
}

const EMPTY_FILTERS: Filters = {
  chain: "", event_type: "", status: "", severity: "", address: "", tx_hash: "",
  block_number: "", token: "", date_from: "", date_to: "", is_large: "",
};

export default function EventExplorerPage() {
  const { current } = useWorkspace();
  const [chains, setChains] = useState<Chain[]>([]);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<Filters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Paginated<BlockchainEvent> | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    chainService.list().then(setChains).catch(() => setChains([]));
  }, []);

  const load = useCallback(async () => {
    if (!current) return;
    setData(null);
    setError("");
    try {
      const query: Record<string, string | number> = { page, page_size: 25 };
      Object.entries(applied).forEach(([key, value]) => {
        if (value) {
          if (key === "date_from") query[key] = `${value}T00:00:00Z`;
          else if (key === "date_to") query[key] = `${value}T23:59:59Z`;
          else query[key] = value;
        }
      });
      setData(await eventService.list(query));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load events");
    }
  }, [current, page, applied]);

  useEffect(() => {
    void load();
  }, [load]);

  const set = (key: keyof Filters) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setFilters((f) => ({ ...f, [key]: e.target.value }));

  return (
    <>
      <PageHeader title="Event explorer" subtitle="Every on-chain occurrence matched to your monitors." />

      <form
        className="cs-card p-3 mb-3"
        onSubmit={(e) => {
          e.preventDefault();
          setPage(1);
          setApplied(filters);
        }}
      >
        <div className="row g-2">
          <div className="col-6 col-md-3 col-xl-2">
            <label className="form-label small mb-1">Chain</label>
            <select className="form-select form-select-sm" value={filters.chain} onChange={set("chain")}>
              <option value="">All chains</option>
              {chains.map((chain) => (
                <option key={chain.slug} value={chain.slug}>{chain.name}</option>
              ))}
            </select>
          </div>
          <div className="col-6 col-md-3 col-xl-2">
            <label className="form-label small mb-1">Event type</label>
            <select className="form-select form-select-sm" value={filters.event_type} onChange={set("event_type")}>
              <option value="">All types</option>
              {EVENT_TYPES.map((type) => (
                <option key={type} value={type}>{eventTypeLabel(type)}</option>
              ))}
            </select>
          </div>
          <div className="col-6 col-md-3 col-xl-2">
            <label className="form-label small mb-1">Status</label>
            <select className="form-select form-select-sm" value={filters.status} onChange={set("status")}>
              <option value="">Any status</option>
              {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="col-6 col-md-3 col-xl-2">
            <label className="form-label small mb-1">Severity</label>
            <select className="form-select form-select-sm" value={filters.severity} onChange={set("severity")}>
              <option value="">Any severity</option>
              {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="col-6 col-md-3 col-xl-2">
            <label className="form-label small mb-1">Large only</label>
            <select className="form-select form-select-sm" value={filters.is_large} onChange={set("is_large")}>
              <option value="">All sizes</option>
              <option value="true">Large transfers</option>
            </select>
          </div>
          <div className="col-6 col-md-3 col-xl-2">
            <label className="form-label small mb-1">Block #</label>
            <input className="form-control form-control-sm" value={filters.block_number} onChange={set("block_number")} inputMode="numeric" />
          </div>
          <div className="col-md-6 col-xl-4">
            <label className="form-label small mb-1">Address (from / to / spender / contract)</label>
            <input className="form-control form-control-sm mono" placeholder="0x…" value={filters.address} onChange={set("address")} />
          </div>
          <div className="col-md-6 col-xl-4">
            <label className="form-label small mb-1">Tx hash</label>
            <input className="form-control form-control-sm mono" placeholder="0x…" value={filters.tx_hash} onChange={set("tx_hash")} />
          </div>
          <div className="col-6 col-md-3 col-xl-2">
            <label className="form-label small mb-1">From date</label>
            <input type="date" className="form-control form-control-sm" value={filters.date_from} onChange={set("date_from")} />
          </div>
          <div className="col-6 col-md-3 col-xl-2">
            <label className="form-label small mb-1">To date</label>
            <input type="date" className="form-control form-control-sm" value={filters.date_to} onChange={set("date_to")} />
          </div>
        </div>
        <div className="d-flex gap-2 mt-3">
          <button className="btn btn-primary btn-sm px-3" type="submit">Apply filters</button>
          <button
            className="btn btn-outline-secondary btn-sm"
            type="button"
            onClick={() => {
              setFilters(EMPTY_FILTERS);
              setApplied(EMPTY_FILTERS);
              setPage(1);
            }}
          >
            Reset
          </button>
        </div>
      </form>

      {error && <div className="alert alert-danger py-2 small">{error}</div>}

      <div className="cs-card">
        {data === null ? (
          <TableSkeleton rows={10} cols={7} />
        ) : data.results.length === 0 ? (
          <EmptyState
            icon="⛓"
            title="No events match"
            body="Adjust the filters, or create a monitor to start capturing events."
            actionLabel="Create monitor"
            actionHref="/app/monitors/wallets/new"
          />
        ) : (
          <>
            <div className="table-scroll">
              <table className="table table-cs">
                <thead>
                  <tr>
                    <th>Type</th><th>Monitor</th><th>Amount</th><th>From → To</th>
                    <th>Chain</th><th>Block</th><th>Status</th><th>Severity</th><th>When</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((event) => (
                    <tr key={event.id}>
                      <td>
                        <Link href={`/app/events/${event.id}`} className="fw-semibold text-body">
                          {eventTypeLabel(event.event_type)}
                        </Link>
                        {event.is_large && <span className="ms-1 badge-severity severity-high">large</span>}
                      </td>
                      <td className="small">{event.monitor_name}</td>
                      <td className="mono small">{formatAmount(event)}</td>
                      <td className="small">
                        <span className="address-chip">{shortAddress(event.from_address) || "—"}</span>
                        <span className="mx-1 text-secondary">→</span>
                        <span className="address-chip">{shortAddress(event.to_address || event.spender_address) || "—"}</span>
                      </td>
                      <td className="small">{event.chain_name}</td>
                      <td className="mono small">{event.block_number.toLocaleString()}</td>
                      <td><StatusBadge status={event.status} /></td>
                      <td><SeverityBadge severity={event.severity} /></td>
                      <td className="small text-secondary">{timeAgo(event.created_at)}</td>
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
