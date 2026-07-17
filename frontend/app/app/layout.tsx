"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import Sidebar from "@/components/app/Sidebar";
import Topbar from "@/components/app/Topbar";
import VerifyEmailBanner from "@/components/app/VerifyEmailBanner";
import { useAuth } from "@/lib/auth-context";
import { useWorkspace } from "@/lib/workspace-context";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const { loading: workspaceLoading, current } = useWorkspace();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login?next=/app");
  }, [loading, user, router]);

  if (loading || (!user && typeof window !== "undefined")) {
    return (
      <div className="d-flex align-items-center justify-content-center min-vh-100">
        <div className="spinner-border text-primary" role="status" aria-label="Loading" />
      </div>
    );
  }

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main">
        <Topbar />
        <VerifyEmailBanner />
        <main className="app-content">
          {workspaceLoading ? (
            <div className="d-flex justify-content-center py-5">
              <div className="spinner-border text-primary" role="status" aria-label="Loading workspace" />
            </div>
          ) : current ? (
            children
          ) : (
            <div className="empty-state">
              <div className="empty-icon">▣</div>
              <h6>No workspace selected</h6>
              <p className="small">Create a workspace from the switcher in the top bar.</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
