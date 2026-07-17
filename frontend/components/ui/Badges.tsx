export function SeverityBadge({ severity }: { severity: string }) {
  return <span className={`badge-severity severity-${severity}`}>{severity}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge-status st-${status}`}>{status.replace(/_/g, " ")}</span>;
}

export function ActiveBadge({ active }: { active: boolean }) {
  return (
    <span className={`badge-status ${active ? "st-active" : "st-paused"}`}>
      {active ? "active" : "paused"}
    </span>
  );
}

export function HealthDot({ status }: { status: string }) {
  const dot =
    status === "healthy" ? "dot-green" : status === "degraded" ? "dot-amber" : status === "unhealthy" ? "dot-red" : "dot-grey";
  return <span className={`status-dot ${dot}`} aria-hidden="true" />;
}
