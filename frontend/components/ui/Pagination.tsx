"use client";

export default function Pagination({
  count,
  page,
  pageSize = 25,
  onPage,
}: {
  count: number;
  page: number;
  pageSize?: number;
  onPage: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(count / pageSize));
  if (pages <= 1) return null;

  return (
    <nav className="d-flex align-items-center justify-content-between p-2 border-top" style={{ borderColor: "var(--cs-border)" }} aria-label="pagination">
      <span className="small text-secondary ms-2">
        Page {page} of {pages} · {count.toLocaleString()} records
      </span>
      <div className="btn-group btn-group-sm me-2">
        <button className="btn btn-outline-secondary" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          ← Prev
        </button>
        <button className="btn btn-outline-secondary" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next →
        </button>
      </div>
    </nav>
  );
}
