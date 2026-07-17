"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { authService } from "@/services/auth";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

function VerifyContent() {
  const params = useSearchParams();
  const token = params.get("token") || "";
  const { reloadUser } = useAuth();
  const [state, setState] = useState<"working" | "done" | "error">("working");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setState("error");
      setMessage("This verification link is incomplete.");
      return;
    }
    (async () => {
      try {
        const result = await authService.verifyEmail(token);
        setMessage(result.detail);
        setState("done");
        await reloadUser();
      } catch (err) {
        setMessage(err instanceof ApiError ? err.message : "Verification failed.");
        setState("error");
      }
    })();
  }, [token, reloadUser]);

  return (
    <div className="cs-card p-4 p-md-5 shadow-lg text-center">
      {state === "working" && (
        <>
          <div className="spinner-border text-primary mb-3" role="status" aria-label="Verifying" />
          <h1 className="h5 fw-bold">Verifying your email…</h1>
        </>
      )}
      {state === "done" && (
        <>
          <div className="fs-1 mb-2">✓</div>
          <h1 className="h5 fw-bold mb-2">Email verified</h1>
          <p className="text-secondary small">{message}</p>
          <Link href="/app" className="btn btn-primary w-100 mt-2">Open dashboard</Link>
        </>
      )}
      {state === "error" && (
        <>
          <div className="fs-1 mb-2">✕</div>
          <h1 className="h5 fw-bold mb-2">Verification failed</h1>
          <p className="text-secondary small">{message}</p>
          <p className="small text-secondary mb-0">
            Signed in? Resend the email from the banner in your dashboard.{" "}
            <Link href="/app">Go to dashboard</Link>
          </p>
        </>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyContent />
    </Suspense>
  );
}
