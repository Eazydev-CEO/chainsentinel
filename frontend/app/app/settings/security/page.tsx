"use client";

import { useCallback, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import PageHeader from "@/components/app/PageHeader";
import { TableSkeleton } from "@/components/ui/Skeletons";
import { ApiError } from "@/lib/api";
import { formatDate, timeAgo } from "@/lib/format";
import { authService } from "@/services/auth";
import type { UserSession } from "@/types";

const schema = z
  .object({
    current_password: z.string().min(1, "Required"),
    new_password: z.string().min(10, "At least 10 characters"),
    confirm: z.string(),
  })
  .refine((v) => v.new_password === v.confirm, {
    path: ["confirm"],
    message: "Passwords do not match",
  });

type FormValues = z.infer<typeof schema>;

export default function SecuritySettingsPage() {
  const [sessions, setSessions] = useState<UserSession[] | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const loadSessions = useCallback(async () => {
    try {
      setSessions(await authService.sessions());
    } catch {
      setSessions([]);
    }
  }, []);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  const onSubmit = async (values: FormValues) => {
    setError("");
    setNotice("");
    try {
      await authService.changePassword(values.current_password, values.new_password);
      setNotice("Password changed. Other devices were signed out.");
      reset();
      await loadSessions();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Change failed.");
    }
  };

  return (
    <div style={{ maxWidth: 760 }}>
      <PageHeader title="Security" subtitle="Password and active devices." />

      {notice && <div className="alert alert-success py-2 small">{notice}</div>}
      {error && <div className="alert alert-danger py-2 small">{error}</div>}

      <div className="cs-card p-4 mb-4">
        <h6 className="fw-semibold mb-3">Change password</h6>
        <form onSubmit={handleSubmit(onSubmit)} noValidate>
          <div className="row g-3">
            <div className="col-md-4">
              <label className="form-label">Current password</label>
              <input type="password" autoComplete="current-password" className={`form-control ${errors.current_password ? "is-invalid" : ""}`} {...register("current_password")} />
              {errors.current_password && <div className="invalid-feedback">{errors.current_password.message}</div>}
            </div>
            <div className="col-md-4">
              <label className="form-label">New password</label>
              <input type="password" autoComplete="new-password" className={`form-control ${errors.new_password ? "is-invalid" : ""}`} {...register("new_password")} />
              {errors.new_password && <div className="invalid-feedback">{errors.new_password.message}</div>}
            </div>
            <div className="col-md-4">
              <label className="form-label">Confirm</label>
              <input type="password" autoComplete="new-password" className={`form-control ${errors.confirm ? "is-invalid" : ""}`} {...register("confirm")} />
              {errors.confirm && <div className="invalid-feedback">{errors.confirm.message}</div>}
            </div>
          </div>
          <button className="btn btn-primary mt-3" disabled={isSubmitting}>
            {isSubmitting ? "Updating…" : "Update password"}
          </button>
        </form>
      </div>

      <div className="cs-card">
        <div className="p-3 pb-2 d-flex justify-content-between align-items-center">
          <h6 className="fw-semibold mb-0">Active sessions</h6>
          <button
            className="btn btn-outline-secondary btn-sm"
            onClick={async () => {
              await authService.revokeOtherSessions();
              await loadSessions();
            }}
          >
            Sign out other devices
          </button>
        </div>
        {sessions === null ? (
          <TableSkeleton rows={3} cols={4} />
        ) : (
          <div className="table-scroll">
            <table className="table table-cs">
              <thead>
                <tr><th>Device</th><th>IP</th><th>Signed in</th><th>Last seen</th><th></th></tr>
              </thead>
              <tbody>
                {sessions.map((session) => (
                  <tr key={session.id}>
                    <td className="small" style={{ maxWidth: 320 }}>
                      {session.is_current && <span className="badge-status st-active me-2">this device</span>}
                      <span className="text-secondary">{session.user_agent || "unknown agent"}</span>
                    </td>
                    <td className="small">{session.ip_address || "—"}</td>
                    <td className="small text-secondary">{formatDate(session.created_at)}</td>
                    <td className="small text-secondary">{timeAgo(session.last_seen_at)}</td>
                    <td className="text-end">
                      {!session.is_current && (
                        <button
                          className="btn btn-outline-danger btn-sm"
                          onClick={async () => {
                            await authService.revokeSession(session.id);
                            await loadSessions();
                          }}
                        >
                          Revoke
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
