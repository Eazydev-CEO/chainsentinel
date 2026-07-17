import Link from "next/link";

export default function EmptyState({
  icon = "◎",
  title,
  body,
  actionLabel,
  actionHref,
}: {
  icon?: string;
  title: string;
  body?: string;
  actionLabel?: string;
  actionHref?: string;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon" aria-hidden="true">
        {icon}
      </div>
      <h6 className="mb-1 text-body">{title}</h6>
      {body && <p className="mb-3 small">{body}</p>}
      {actionLabel && actionHref && (
        <Link href={actionHref} className="btn btn-primary btn-sm">
          {actionLabel}
        </Link>
      )}
    </div>
  );
}
