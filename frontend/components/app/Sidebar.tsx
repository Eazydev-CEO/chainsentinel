"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const SECTIONS: { title: string; items: { href: string; label: string; icon: string }[] }[] = [
  {
    title: "Overview",
    items: [
      { href: "/app", label: "Dashboard", icon: "▦" },
      { href: "/app/analytics", label: "Analytics", icon: "◔" },
      { href: "/app/events", label: "Event explorer", icon: "⛓" },
    ],
  },
  {
    title: "Monitoring",
    items: [
      { href: "/app/monitors/wallets", label: "Wallet monitors", icon: "👛" },
      { href: "/app/monitors/contracts", label: "Contract monitors", icon: "📜" },
      { href: "/app/providers", label: "RPC providers", icon: "🖧" },
    ],
  },
  {
    title: "Alerting",
    items: [
      { href: "/app/alerts", label: "Alerts", icon: "🔔" },
      { href: "/app/alert-rules", label: "Alert rules", icon: "⚙" },
      { href: "/app/webhooks", label: "Webhooks", icon: "⇄" },
      { href: "/app/notifications", label: "Notifications", icon: "✉" },
    ],
  },
  {
    title: "Settings",
    items: [
      { href: "/app/settings/workspace", label: "Workspace", icon: "▣" },
      { href: "/app/settings/members", label: "Members", icon: "👥" },
      { href: "/app/settings/api-keys", label: "API keys", icon: "🔑" },
      { href: "/app/settings/profile", label: "Profile", icon: "☺" },
      { href: "/app/settings/security", label: "Security", icon: "🛡" },
    ],
  },
];

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const isActive = (href: string) =>
    href === "/app" ? pathname === "/app" : pathname.startsWith(href);

  return (
    <>
      <div className="px-3 py-3 border-bottom" style={{ borderColor: "var(--cs-border)" }}>
        <Link href="/" className="fw-bold fs-6 text-body" onClick={onNavigate}>
          ⛓ Chain<span style={{ color: "var(--cs-accent)" }}>Sentinel</span>
        </Link>
      </div>
      <nav className="px-2 pb-4 flex-grow-1" aria-label="Dashboard navigation">
        {SECTIONS.map((section) => (
          <div key={section.title}>
            <div className="nav-section">{section.title}</div>
            <ul className="nav flex-column gap-1">
              {section.items.map((item) => (
                <li className="nav-item" key={item.href}>
                  <Link
                    href={item.href}
                    className={`nav-link ${isActive(item.href) ? "active" : ""}`}
                    onClick={onNavigate}
                  >
                    <span aria-hidden="true" style={{ width: 18, textAlign: "center" }}>
                      {item.icon}
                    </span>
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      <div className="px-3 py-3 border-top small text-secondary" style={{ borderColor: "var(--cs-border)" }}>
        <a href="/api/v1/docs/" className="text-secondary">API docs ↗</a>
      </div>
    </>
  );
}

export default function Sidebar() {
  return (
    <aside className="app-sidebar d-none d-lg-flex">
      <SidebarNav />
    </aside>
  );
}
