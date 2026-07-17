export function TableSkeleton({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="p-3" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, r) => (
        <div className="d-flex gap-3 mb-3" key={r}>
          {Array.from({ length: cols }).map((__, c) => (
            <div className="skeleton flex-fill" key={c} style={{ height: 14 }} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function CardsSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="row g-3" aria-busy="true" aria-label="Loading">
      {Array.from({ length: count }).map((_, i) => (
        <div className="col-6 col-lg-3" key={i}>
          <div className="stat-card">
            <div className="skeleton mb-2" style={{ width: "55%" }} />
            <div className="skeleton" style={{ height: 26, width: "40%" }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function BlockSkeleton({ height = 220 }: { height?: number }) {
  return <div className="skeleton w-100" style={{ height }} aria-busy="true" />;
}
