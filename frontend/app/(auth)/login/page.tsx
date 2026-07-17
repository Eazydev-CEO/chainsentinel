"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";

const schema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

type FormValues = z.infer<typeof schema>;

function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState("");
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setError("");
    try {
      await login(values.email, values.password);
      router.push(params.get("next") || "/app");
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign-in failed. Try again.");
    }
  };

  return (
    <div className="cs-card p-4 p-md-5 shadow-lg">
      <h1 className="h4 fw-bold mb-1">Welcome back</h1>
      <p className="text-secondary small mb-4">Sign in to your monitoring workspace.</p>

      {error && <div className="alert alert-danger py-2 small" role="alert">{error}</div>}

      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <div className="mb-3">
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
        <div className="mb-4">
          <div className="d-flex justify-content-between">
            <label className="form-label" htmlFor="password">Password</label>
            <Link href="/forgot-password" className="small">Forgot password?</Link>
          </div>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            className={`form-control ${errors.password ? "is-invalid" : ""}`}
            {...register("password")}
          />
          {errors.password && <div className="invalid-feedback">{errors.password.message}</div>}
        </div>
        <button className="btn btn-primary w-100" disabled={isSubmitting}>
          {isSubmitting ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <p className="text-center small text-secondary mt-4 mb-0">
        New here? <Link href="/register">Create a workspace</Link>
      </p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
