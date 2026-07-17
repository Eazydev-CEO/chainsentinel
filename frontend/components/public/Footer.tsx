import Link from "next/link";

const COLUMNS: { heading: string; links: { href: string; label: string; external?: boolean }[] }[] = [
  {
    heading: "Product",
    links: [
      { href: "/features", label: "Features" },
      { href: "/chains", label: "Supported chains" },
      { href: "/how-it-works", label: "How it works" },
      { href: "/pricing", label: "Pricing" },
    ],
  },
  {
    heading: "Developers",
    links: [
      { href: "/docs", label: "Documentation" },
      { href: "/api/v1/docs/", label: "API reference ↗", external: true },
      { href: "/docs#webhooks", label: "Webhooks" },
    ],
  },
  {
    heading: "Company",
    links: [
      { href: "/contact", label: "Contact" },
      { href: "/privacy", label: "Privacy policy" },
      { href: "/terms", label: "Terms of service" },
    ],
  },
  {
    heading: "Account",
    links: [
      { href: "/login", label: "Sign in" },
      { href: "/register", label: "Create workspace" },
    ],
  },
];

export default function Footer() {
  return (
    <footer className="footer-public mt-auto pt-5 pb-4" aria-label="Site footer">
      <div className="container">
        <div className="row g-4 g-lg-5 pb-2">
          <div className="col-lg-4">
            <div className="fw-bold fs-5 mb-2">
              ⛓ Chain<span style={{ color: "var(--cs-accent)" }}>Sentinel</span>
            </div>
            <p className="footer-tagline small mb-3">
              Real-time wallet, token, approval, and smart-contract monitoring across EVM
              networks. Built for teams that can&apos;t afford to miss a transaction.
            </p>
            <div className="d-flex flex-wrap gap-2">
              <span className="chain-pill" style={{ fontSize: "0.75rem", padding: "0.3rem 0.7rem" }}>
                <span className="status-dot dot-green" aria-hidden="true" />
                6 EVM networks
              </span>
              <span className="chain-pill" style={{ fontSize: "0.75rem", padding: "0.3rem 0.7rem" }}>
                🛡 Read-only by design
              </span>
            </div>
          </div>

          {COLUMNS.map((column) => (
            <div className="col-6 col-lg-2" key={column.heading}>
              <h6 className="footer-heading">{column.heading}</h6>
              <ul className="list-unstyled small d-grid gap-2 mb-0">
                {column.links.map((link) =>
                  link.external ? (
                    <li key={link.label}>
                      <a className="footer-link" href={link.href}>
                        {link.label}
                      </a>
                    </li>
                  ) : (
                    <li key={link.label}>
                      <Link className="footer-link" href={link.href}>
                        {link.label}
                      </Link>
                    </li>
                  )
                )}
              </ul>
            </div>
          ))}
        </div>

        <hr className="my-4" />

        <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-2 small">
          <span className="footer-note">
            © {new Date().getFullYear()} ChainSentinel. All rights reserved.
          </span>
          <span className="footer-note d-flex align-items-center gap-2">
            <span className="status-dot dot-green" aria-hidden="true" />
            We never hold private keys — monitoring is strictly read-only.
          </span>
        </div>
      </div>
    </footer>
  );
}
