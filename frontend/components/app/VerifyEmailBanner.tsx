"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { authService } from "@/services/auth";

export default function VerifyEmailBanner() {
  const { user } = useAuth();
  const [sent, setSent] = useState(false);

  if (!user || user.is_email_verified) return null;

  return (
    <div className="alert alert-warning rounded-0 mb-0 py-2 small d-flex flex-wrap align-items-center gap-2" role="alert">
      <span>
        ✉ Verify your email address to create monitors, webhooks and API keys.
      </span>
      <button
        className="btn btn-sm btn-outline-dark"
        disabled={sent}
        onClick={async () => {
          await authService.resendVerification();
          setSent(true);
        }}
      >
        {sent ? "Sent — check your inbox" : "Resend verification email"}
      </button>
    </div>
  );
}
