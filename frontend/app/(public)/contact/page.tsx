"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { contactService } from "@/services/platform";
import { ApiError } from "@/lib/api";

const schema = z.object({
  name: z.string().max(120).optional().or(z.literal("")),
  email: z.string().email("Enter a valid email address"),
  subject: z.string().max(180).optional().or(z.literal("")),
  message: z.string().min(10, "Tell us a bit more (10+ characters)").max(5000),
});

type FormValues = z.infer<typeof schema>;

export default function ContactPage() {
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setError("");
    try {
      await contactService.send({
        name: values.name || "",
        email: values.email,
        subject: values.subject || "",
        message: values.message,
      });
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    }
  };

  return (
    <div className="container py-5" style={{ maxWidth: 640 }}>
      <div className="text-center mb-4">
        <span className="section-eyebrow">Contact</span>
        <h1 className="fw-bold mt-2">Talk to the team</h1>
        <p className="text-secondary">
          Product questions, enterprise plans, security reports — we read everything.
        </p>
      </div>

      {sent ? (
        <div className="cs-card p-5 text-center">
          <div className="fs-1 mb-2">✓</div>
          <h5>Message received</h5>
          <p className="text-secondary mb-0">We&apos;ll reply to your email shortly.</p>
        </div>
      ) : (
        <form className="cs-card p-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          {error && <div className="alert alert-danger py-2 small">{error}</div>}
          <div className="row g-3">
            <div className="col-md-6">
              <label className="form-label" htmlFor="contact-name">Name</label>
              <input id="contact-name" className="form-control" {...register("name")} />
            </div>
            <div className="col-md-6">
              <label className="form-label" htmlFor="contact-email">Email *</label>
              <input
                id="contact-email"
                type="email"
                className={`form-control ${errors.email ? "is-invalid" : ""}`}
                {...register("email")}
              />
              {errors.email && <div className="invalid-feedback">{errors.email.message}</div>}
            </div>
            <div className="col-12">
              <label className="form-label" htmlFor="contact-subject">Subject</label>
              <input id="contact-subject" className="form-control" {...register("subject")} />
            </div>
            <div className="col-12">
              <label className="form-label" htmlFor="contact-message">Message *</label>
              <textarea
                id="contact-message"
                rows={6}
                className={`form-control ${errors.message ? "is-invalid" : ""}`}
                {...register("message")}
              />
              {errors.message && <div className="invalid-feedback">{errors.message.message}</div>}
            </div>
            <div className="col-12">
              <button className="btn btn-primary px-4" disabled={isSubmitting}>
                {isSubmitting ? "Sending…" : "Send message"}
              </button>
            </div>
          </div>
        </form>
      )}
    </div>
  );
}
