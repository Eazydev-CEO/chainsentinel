"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { authService } from "@/services/auth";
import { ApiError } from "@/lib/api";

const schema = z
  .object({
    password: z.string().min(10, "At least 10 characters"),
    confirm: z.string(),
  })
  .refine((data) => data.password === data.confirm, {
    path: ["confirm"],
    message: "Passwords do not match",
  });

type FormValues = z.infer<typeof schema>;

function ResetForm() {
  const params = useSearchParams();
  const token = params.get("token") || "";
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setError("");
    try {
      await authService.resetPassword(token, values.password);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Reset failed. Request a new link.");
    }
  };

  if (!token) {
    return (
      <div className="alert alert-warning small">
        This reset link is incomplete. <Link href="/forgot-password">Request a new one</Link>.
      </div>
    );
  }

  return (
    <div className="cs-card p-4 p-md-5 shadow-lg">
      <h1 className="h4 fw-bold mb-1">Choose a new password</h1>
      <p className="text-secondary small mb-4">This link can be used once and expires quickly.</p>

      {done ? (
        <>
          <div className="alert alert-success py-3 small">Password updated.</div>
          <Link href="/login" className="btn btn-primary w-100">Sign in</Link>
        </>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} noValidate>
          {error && <div className="alert alert-danger py-2 small">{error}</div>}
          <div className="mb-3">
            <label className="form-label" htmlFor="password">New password</label>
            <input
              id="password"
              type="password"
              autoComplete="new-password"
              className={`form-control ${errors.password ? "is-invalid" : ""}`}
              {...register("password")}
            />
            {errors.password && <div className="invalid-feedback">{errors.password.message}</div>}
          </div>
          <div className="mb-4">
            <label className="form-label" htmlFor="confirm">Confirm password</label>
            <input
              id="confirm"
              type="password"
              autoComplete="new-password"
              className={`form-control ${errors.confirm ? "is-invalid" : ""}`}
              {...register("confirm")}
            />
            {errors.confirm && <div className="invalid-feedback">{errors.confirm.message}</div>}
          </div>
          <button className="btn btn-primary w-100" disabled={isSubmitting}>
            {isSubmitting ? "Saving…" : "Set new password"}
          </button>
        </form>
      )}
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetForm />
    </Suspense>
  );
}
