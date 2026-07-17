export default function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-4">
      <div>
        <h1 className="page-title mb-0">{title}</h1>
        {subtitle && <p className="text-secondary small mb-0 mt-1">{subtitle}</p>}
      </div>
      {actions && <div className="d-flex gap-2 flex-wrap">{actions}</div>}
    </div>
  );
}
