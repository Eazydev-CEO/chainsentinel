"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

const LINKS = [
  { href: "/features", label: "Features" },
  { href: "/chains", label: "Chains" },
  { href: "/how-it-works", label: "How it works" },
  { href: "/pricing", label: "Pricing" },
  { href: "/docs", label: "Docs" },
  { href: "/contact", label: "Contact" },
];

export default function PublicNavbar() {
  const pathname = usePathname();
  const { user, loading } = useAuth();

  return (
    <nav className="navbar navbar-expand-lg sticky-top app-topbar" aria-label="Main navigation">
      <div className="container">
        <Link className="navbar-brand fw-bold" href="/">
          ⛓ Chain<span style={{ color: "var(--cs-accent)" }}>Sentinel</span>
        </Link>
        <button
          className="navbar-toggler"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#publicNav"
          aria-controls="publicNav"
          aria-expanded="false"
          aria-label="Toggle navigation"
        >
          <span className="navbar-toggler-icon" />
        </button>
        <div className="collapse navbar-collapse" id="publicNav">
          <ul className="navbar-nav mx-auto mb-2 mb-lg-0">
            {LINKS.map((link) => (
              <li className="nav-item" key={link.href}>
                <Link
                  className={`nav-link ${pathname === link.href ? "active fw-semibold" : ""}`}
                  href={link.href}
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
          <div className="d-flex gap-2">
            {!loading && user ? (
              <Link href="/app" className="btn btn-primary btn-sm px-3">
                Open dashboard
              </Link>
            ) : (
              <>
                <Link href="/login" className="btn btn-outline-secondary btn-sm px-3">
                  Sign in
                </Link>
                <Link href="/register" className="btn btn-primary btn-sm px-3">
                  Start monitoring
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
