"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { useWorkspace } from "@/lib/workspace-context";
import { workspaceService } from "@/services/workspaces";
import { ApiError } from "@/lib/api";

function AcceptInviteContent() {
  const params = useSearchParams();
  const token = params.get("token") || "";
  const router = useRouter();
  const { user, loading } = useAuth();
  const { reloadWorkspaces, switchWorkspace } = useWorkspace();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const accept = async () => {
    setBusy(true);
    setError("");
    try {
      const workspace = await workspaceService.acceptInvite(token);
      await reloadWorkspaces();
      switchWorkspace(workspace.id);
      router.push("/app");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not accept the invitation.");
    } finally {
      setBusy(false);
    }
  };

  if (!token) {
    return <div className="alert alert-warning small">This invitation link is incomplete.</div>;
  }

  return (
    <div className="cs-card p-4 p-md-5 shadow-lg text-center">
      <div className="fs-1 mb-2">✉</div>
      <h1 className="h5 fw-bold mb-2">Workspace invitation</h1>
      {error && <div className="alert alert-danger py-2 small">{error}</div>}

      {loading ? (
        <div className="spinner-border text-primary" role="status" aria-label="Loading" />
      ) : user ? (
        <>
          <p className="text-secondary small">
            Accept this invitation with your account <strong>{user.email}</strong>? The invite
            must have been sent to this exact address.
          </p>
          <button className="btn btn-primary w-100" onClick={accept} disabled={busy}>
            {busy ? "Joining…" : "Accept invitation"}
          </button>
        </>
      ) : (
        <>
          <p className="text-secondary small">
            Sign in (or create an account) with the invited email address first — then reopen
            this link.
          </p>
          <div className="d-grid gap-2">
            <Link href={`/login?next=/accept-invite?token=${encodeURIComponent(token)}`} className="btn btn-primary">
              Sign in
            </Link>
            <Link href="/register" className="btn btn-outline-secondary">
              Create an account
            </Link>
          </div>
        </>
      )}
    </div>
  );
}

export default function AcceptInvitePage() {
  return (
    <Suspense>
      <AcceptInviteContent />
    </Suspense>
  );
}
