"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";

const schema = z.object({
  first_name: z.string().max(100).optional().or(z.literal("")),
  last_name: z.string().max(100).optional().or(z.literal("")),
  email: z.string().email("Enter a valid email"),
  password: z
    .string()
    .min(10, "At least 10 characters")
    .regex(/[^0-9]/, "Cannot be entirely numeric"),
  workspace_name: z.string().max(100).optional().or(z.literal("")),
});

type FormValues = z.infer<typeof schema>;

export default function RegisterPage() {
  const { register: registerAccount } = useAuth();
  const router = useRouter();
  const [error, setError] = useState("");
  const {
    register,
    handleSubmit,
    setError: setFieldError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setError("");
    try {
      await registerAccount(values);
      router.push("/app");
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError) {
        const fields = err.fieldErrors();
        let assigned = false;
        (Object.keys(fields) as (keyof FormValues)[]).forEach((key) => {
          if (["email", "password", "first_name", "last_name", "workspace_name"].includes(key)) {
            setFieldError(key, { message: fields[key] });
            assigned = true;
          }
        });
        if (!assigned) setError(err.message);
      } else {
        setError("Registration failed. Try again.");
      }
    }
  };

  return (
    <div className="cs-card p-4 p-md-5 shadow-lg">
      <h1 className="h4 fw-bold mb-1">Create your workspace</h1>
      <p className="text-secondary small mb-4">
        Free during early access. No card, no keys — just monitoring.
      </p>

      {error && <div className="alert alert-danger py-2 small" role="alert">{error}</div>}

      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <div className="row g-3 mb-3">
          <div className="col-6">
            <label className="form-label" htmlFor="first_name">First name</label>
            <input id="first_name" className="form-control" autoComplete="given-name" {...register("first_name")} />
          </div>
          <div className="col-6">
            <label className="form-label" htmlFor="last_name">Last name</label>
            <input id="last_name" className="form-control" autoComplete="family-name" {...register("last_name")} />
          </div>
        </div>
        <div className="mb-3">
          <label className="form-label" htmlFor="email">Work email</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            className={`form-control ${errors.email ? "is-invalid" : ""}`}
            {...register("email")}
          />
          {errors.email && <div className="invalid-feedback">{errors.email.message}</div>}
        </div>
        <div className="mb-3">
          <label className="form-label" htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            autoComplete="new-password"
            className={`form-control ${errors.password ? "is-invalid" : ""}`}
            {...register("password")}
          />
          {errors.password && <div className="invalid-feedback">{errors.password.message}</div>}
          <div className="form-hint mt-1">10+ characters, not entirely numeric, not a common password.</div>
        </div>
        <div className="mb-4">
          <label className="form-label" htmlFor="workspace_name">Workspace name (optional)</label>
          <input
            id="workspace_name"
            className="form-control"
            placeholder="e.g. Acme Treasury"
            {...register("workspace_name")}
          />
        </div>
        <button className="btn btn-primary w-100" disabled={isSubmitting}>
          {isSubmitting ? "Creating…" : "Create workspace"}
        </button>
      </form>

      <p className="text-center small text-secondary mt-4 mb-0">
        Already have an account? <Link href="/login">Sign in</Link>
      </p>
    </div>
  );
}
