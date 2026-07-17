"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import PageHeader from "@/components/app/PageHeader";
import CopyButton from "@/components/ui/CopyButton";
import { ApiError } from "@/lib/api";
import { webhookService } from "@/services/platform";
import type { WebhookEndpoint } from "@/types";

const EVENT_TYPES = [
  ["alert.triggered", "Alert triggered"],
  ["alert.resolved", "Alert resolved"],
  ["event.confirmed", "Blockchain event confirmed"],
  ["monitor.paused", "Monitor paused"],
  ["provider.unhealthy", "RPC provider unhealthy"],
  ["test.ping", "Test ping"],
] as const;

const schema = z.object({
  name: z.string().min(1, "Name the endpoint").max(120),
  url: z.string().url("Enter a valid URL").max(500),
  event_types: z.array(z.string()).min(1, "Pick at least one event type"),
  max_retries: z.coerce.number().min(0).max(10),
  timeout_seconds: z.coerce.number().min(1).max(30),
});

type FormValues = z.infer<typeof schema>;

export default function NewWebhookPage() {
  const router = useRouter();
  const [created, setCreated] = useState<WebhookEndpoint | null>(null);
  const [error, setError] = useState("");
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    setError: setFieldError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      event_types: ["alert.triggered"],
      max_retries: 5,
      timeout_seconds: 10,
    },
  });

  const selected = watch("event_types");
  const toggle = (value: string) =>
    setValue(
      "event_types",
      selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value],
      { shouldValidate: true }
    );

  const onSubmit = async (values: FormValues) => {
    setError("");
    try {
      setCreated(await webhookService.create(values));
    } catch (err) {
      if (err instanceof ApiError) {
        const fields = err.fieldErrors();
        if (fields.url) setFieldError("url", { message: fields.url });
        else setError(err.message);
      } else {
        setError("Creation failed.");
      }
    }
  };

  if (created) {
    return (
      <div style={{ maxWidth: 720 }}>
        <PageHeader title="Endpoint created" subtitle={created.name} />
        <div className="cs-card p-4">
          <div className="alert alert-warning small">
            <strong>Copy the signing secret now.</strong> For security it is encrypted at rest
            and can never be shown again — only regenerated.
          </div>
          <label className="form-label">Signing secret</label>
          <div className="d-flex gap-2 mb-4">
            <input className="form-control mono" readOnly value={created.secret || ""} />
            <CopyButton value={created.secret || ""} />
          </div>
          <div className="d-flex gap-2">
            <Link href={`/app/webhooks/${created.id}`} className="btn btn-primary">
              Go to endpoint
            </Link>
            <button className="btn btn-outline-secondary" onClick={() => router.push("/app/webhooks")}>
              Back to list
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 720 }}>
      <PageHeader title="New webhook endpoint" subtitle="Destination must be a public https(s) URL — private networks are blocked." />
      <form className="cs-card p-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        {error && <div className="alert alert-danger py-2 small">{error}</div>}
        <div className="mb-3">
          <label className="form-label">Name *</label>
          <input className={`form-control ${errors.name ? "is-invalid" : ""}`} placeholder="e.g. Ops incident receiver" {...register("name")} />
          {errors.name && <div className="invalid-feedback">{errors.name.message}</div>}
        </div>
        <div className="mb-3">
          <label className="form-label">Destination URL *</label>
          <input className={`form-control mono ${errors.url ? "is-invalid" : ""}`} placeholder="https://example.com/webhooks/chainsentinel" {...register("url")} />
          {errors.url && <div className="invalid-feedback">{errors.url.message}</div>}
        </div>
        <div className="mb-3">
          <label className="form-label d-block">Subscribed events *</label>
          <div className="d-grid gap-2">
            {EVENT_TYPES.map(([value, label]) => (
              <label className="form-check" key={value}>
                <input
                  type="checkbox"
                  className="form-check-input"
                  checked={selected.includes(value)}
                  onChange={() => toggle(value)}
                />
                <span className="form-check-label small">
                  <code>{value}</code> — {label}
                </span>
              </label>
            ))}
          </div>
          {errors.event_types && <div className="text-danger small mt-1">{errors.event_types.message}</div>}
        </div>
        <div className="row g-3 mb-4">
          <div className="col-6">
            <label className="form-label">Retry limit</label>
            <input type="number" min={0} max={10} className="form-control" {...register("max_retries")} />
            <div className="form-hint mt-1">Exponential backoff: 1m, 2m, 4m…</div>
          </div>
          <div className="col-6">
            <label className="form-label">Timeout (seconds)</label>
            <input type="number" min={1} max={30} className="form-control" {...register("timeout_seconds")} />
          </div>
        </div>
        <div className="d-flex gap-2">
          <button className="btn btn-primary px-4" disabled={isSubmitting}>
            {isSubmitting ? "Creating…" : "Create endpoint"}
          </button>
          <button type="button" className="btn btn-outline-secondary" onClick={() => router.back()}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
