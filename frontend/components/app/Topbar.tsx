"use client";

import Link from "next/link";
import { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { promptDialog, toast } from "@/lib/dialogs";
import { useWorkspace } from "@/lib/workspace-context";
import { workspaceService } from "@/services/workspaces";
import NotificationBell from "./NotificationBell";
import { SidebarNav } from "./Sidebar";

export default function Topbar() {
  const { user, logout } = useAuth();
  const { workspaces, current, switchWorkspace, reloadWorkspaces } = useWorkspace();
  const [creating, setCreating] = useState(false);

  const createWorkspace = async () => {
    const name = await promptDialog({
      title: "New workspace",
      text: "Workspaces isolate monitors, alerts and members.",
      placeholder: "e.g. Acme Treasury",
      confirmText: "Create workspace",
      validate: (value) => (value.trim() ? undefined : "Give the workspace a name."),
    });
    if (!name?.trim()) return;
    setCreating(true);
    try {
      const workspace = await workspaceService.create(name.trim());
      await reloadWorkspaces();
      switchWorkspace(workspace.id);
      toast(`Workspace “${workspace.name}” created`);
    } finally {
      setCreating(false);
    }
  };

  return (
    <header className="app-topbar">
      <div className="d-flex align-items-center gap-2 px-3 py-2">
        {/* Mobile menu */}
        <button
          className="btn btn-outline-secondary btn-sm d-lg-none"
          type="button"
          data-bs-toggle="offcanvas"
          data-bs-target="#mobileSidebar"
          aria-controls="mobileSidebar"
          aria-label="Open navigation"
        >
          ☰
        </button>

        {/* Workspace switcher */}
        <div className="dropdown">
          <button
            className="btn btn-outline-secondary btn-sm dropdown-toggle d-flex align-items-center gap-2"
            data-bs-toggle="dropdown"
            aria-expanded="false"
          >
            <span className="status-dot dot-green" aria-hidden="true" />
            <span className="text-truncate" style={{ maxWidth: 180 }}>
              {current?.name || "Select workspace"}
            </span>
          </button>
          <ul className="dropdown-menu">
            {workspaces.map((w) => (
              <li key={w.id}>
                <button
                  className={`dropdown-item small ${w.id === current?.id ? "active" : ""}`}
                  onClick={() => switchWorkspace(w.id)}
                >
                  {w.name}
                  <span className="ms-2 text-secondary">({w.role})</span>
                </button>
              </li>
            ))}
            <li><hr className="dropdown-divider" /></li>
            <li>
              <button className="dropdown-item small" onClick={createWorkspace} disabled={creating}>
                + New workspace
              </button>
            </li>
          </ul>
        </div>

        <div className="ms-auto d-flex align-items-center gap-2">
          <NotificationBell />
          <div className="dropdown">
            <button
              className="btn btn-outline-secondary btn-sm dropdown-toggle"
              data-bs-toggle="dropdown"
              aria-expanded="false"
            >
              {user?.first_name || user?.email?.split("@")[0] || "Account"}
            </button>
            <ul className="dropdown-menu dropdown-menu-end">
              <li className="px-3 py-1 small text-secondary">{user?.email}</li>
              <li><hr className="dropdown-divider" /></li>
              <li><Link className="dropdown-item small" href="/app/settings/profile">Profile</Link></li>
              <li><Link className="dropdown-item small" href="/app/settings/security">Security</Link></li>
              <li><hr className="dropdown-divider" /></li>
              <li>
                <button className="dropdown-item small" onClick={() => void logout()}>
                  Sign out
                </button>
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* Mobile offcanvas nav */}
      <div
        className="offcanvas offcanvas-start d-lg-none"
        tabIndex={-1}
        id="mobileSidebar"
        aria-labelledby="mobileSidebarLabel"
        style={{ background: "var(--cs-bg-raised)", width: 264 }}
      >
        <div className="offcanvas-body d-flex flex-column p-0">
          <SidebarNav
            onNavigate={() => {
              document.querySelector<HTMLElement>("#mobileSidebar .btn-close")?.click();
            }}
          />
          <button type="button" className="btn-close d-none" data-bs-dismiss="offcanvas" aria-label="Close" />
        </div>
      </div>
    </header>
  );
}
