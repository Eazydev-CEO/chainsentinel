"use client";

import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { authService } from "@/services/auth";

const schema = z.object({ email: z.string().email("Enter a valid email") });
type FormValues = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    try {
      await authService.forgotPassword(values.email);
    } finally {
      setSent(true); // same UX either way — no account enumeration
    }
  };

  return (
    <div className="cs-card p-4 p-md-5 shadow-lg">
      <h1 className="h4 fw-bold mb-1">Reset your password</h1>
      <p className="text-secondary small mb-4">
        Enter your account email and we&apos;ll send a reset link.
      </p>

      {sent ? (
        <div className="alert alert-success py-3 small mb-0">
          If that email exists, a reset link is on its way. The link expires in 2 hours.
        </div>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} noValidate>
          <div className="mb-4">
            <label className="form-label" htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              className={`form-control ${errors.email ? "is-invalid" : ""}`}
              {...register("email")}
            />
            {errors.email && <div className="invalid-feedback">{errors.email.message}</div>}
          </div>
          <button className="btn btn-primary w-100" disabled={isSubmitting}>
            {isSubmitting ? "Sending…" : "Send reset link"}
          </button>
        </form>
      )}

      <p className="text-center small text-secondary mt-4 mb-0">
        <Link href="/login">← Back to sign in</Link>
      </p>
    </div>
  );
}
