"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import PageHeader from "@/components/app/PageHeader";
import { useAuth } from "@/lib/auth-context";
import { authService } from "@/services/auth";

const schema = z.object({
  first_name: z.string().max(100).optional().or(z.literal("")),
  last_name: z.string().max(100).optional().or(z.literal("")),
  company: z.string().max(150).optional().or(z.literal("")),
  job_title: z.string().max(150).optional().or(z.literal("")),
  timezone: z.string().max(64).optional().or(z.literal("")),
});

type FormValues = z.infer<typeof schema>;

export default function ProfileSettingsPage() {
  const { user, reloadUser } = useAuth();
  const [saved, setSaved] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    values: user
      ? {
          first_name: user.first_name || "",
          last_name: user.last_name || "",
          company: user.profile?.company || "",
          job_title: user.profile?.job_title || "",
          timezone: user.profile?.timezone || "UTC",
        }
      : undefined,
  });

  const onSubmit = async (values: FormValues) => {
    setSaved(false);
    await authService.updateProfile({
      first_name: values.first_name,
      last_name: values.last_name,
      profile: {
        company: values.company || "",
        job_title: values.job_title || "",
        timezone: values.timezone || "UTC",
      },
    });
    await reloadUser();
    setSaved(true);
  };

  return (
    <div style={{ maxWidth: 640 }}>
      <PageHeader title="Profile" subtitle={user?.email} />
      <form className="cs-card p-4" onSubmit={handleSubmit(onSubmit)}>
        {saved && <div className="alert alert-success py-2 small">Profile saved.</div>}
        <div className="row g-3">
          <div className="col-6">
            <label className="form-label">First name</label>
            <input className="form-control" {...register("first_name")} />
          </div>
          <div className="col-6">
            <label className="form-label">Last name</label>
            <input className="form-control" {...register("last_name")} />
          </div>
          <div className="col-6">
            <label className="form-label">Company</label>
            <input className="form-control" {...register("company")} />
          </div>
          <div className="col-6">
            <label className="form-label">Job title</label>
            <input className="form-control" {...register("job_title")} />
          </div>
          <div className="col-6">
            <label className="form-label">Timezone</label>
            <input className="form-control" placeholder="UTC" {...register("timezone")} />
          </div>
          <div className="col-12">
            <label className="form-label">Email</label>
            <input className="form-control" value={user?.email || ""} disabled />
            <div className="form-hint mt-1">
              {user?.is_email_verified ? "✓ Verified" : "Not verified — check your inbox or resend from the banner."}
            </div>
          </div>
        </div>
        <button className="btn btn-primary mt-4 px-4" disabled={isSubmitting}>
          {isSubmitting ? "Saving…" : "Save profile"}
        </button>
      </form>
    </div>
  );
}
