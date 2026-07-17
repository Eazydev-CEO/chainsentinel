"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ApiError } from "@/lib/api";
import { chainService } from "@/services/platform";
import { contractMonitorService } from "@/services/monitors";
import type { AbiEvent, Chain, ContractMonitor } from "@/types";

const ADDRESS_RE = /^0x[0-9a-fA-F]{40}$/;

const schema = z.object({
  name: z.string().min(1, "Name the monitor").max(120),
  label: z.string().max(120).optional().or(z.literal("")),
  address: z.string().regex(ADDRESS_RE, "Must be a 0x-prefixed 40-hex-char address"),
  chain: z.string().min(1, "Pick a chain"),
  severity: z.enum(["info", "low", "medium", "high", "critical"]),
  confirmations_override: z.string().regex(/^\d*$/).optional().or(z.literal("")),
  tags: z.string().max(400).optional().or(z.literal("")),
  notes: z.string().max(2000).optional().or(z.literal("")),
});

type FormValues = z.infer<typeof schema>;

export default function ContractMonitorForm({ monitor }: { monitor?: ContractMonitor }) {
  const router = useRouter();
  const [chains, setChains] = useState<Chain[]>([]);
  const [abiText, setAbiText] = useState("");
  const [abiEvents, setAbiEvents] = useState<AbiEvent[]>(monitor?.available_events || []);
  const [abiStatus, setAbiStatus] = useState<"idle" | "parsing" | "valid" | "invalid">(
    monitor ? "valid" : "idle"
  );
  const [abiError, setAbiError] = useState("");
  const [selectedEvents, setSelectedEvents] = useState<string[]>(monitor?.selected_events || []);
  const [topicFilters, setTopicFilters] = useState<Record<string, Record<string, string>>>(
    monitor?.topic_filters || {}
  );
  const [error, setError] = useState("");

  const {
    register,
    handleSubmit,
    setError: setFieldError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: monitor
      ? {
          name: monitor.name,
          label: monitor.label,
          address: monitor.address,
          chain: monitor.chain,
          severity: monitor.severity,
          confirmations_override: monitor.confirmations_override?.toString() || "",
          tags: (monitor.tags || []).join(", "),
          notes: monitor.notes || "",
        }
      : { severity: "medium", label: "", tags: "", notes: "" },
  });

  useEffect(() => {
    chainService.list().then((all) => setChains(all.filter((c) => c.is_active))).catch(() => setChains([]));
  }, []);

  const parseAbi = async (text: string) => {
    if (!text.trim()) {
      setAbiStatus(monitor ? "valid" : "idle");
      setAbiError("");
      if (!monitor) setAbiEvents([]);
      return;
    }
    setAbiStatus("parsing");
    setAbiError("");
    try {
      const result = await contractMonitorService.parseAbi(text);
      setAbiEvents(result.events);
      setAbiStatus("valid");
      setSelectedEvents((previous) => previous.filter((name) => result.events.some((e) => e.name === name)));
    } catch (err) {
      setAbiStatus("invalid");
      setAbiEvents([]);
      if (err instanceof ApiError) {
        const fields = err.fieldErrors();
        setAbiError(fields.abi || err.message);
      } else {
        setAbiError("Could not parse the ABI.");
      }
    }
  };

  const onAbiFile = (file: File) => {
    if (file.size > 512 * 1024) {
      setAbiStatus("invalid");
      setAbiError("ABI file is too large (max 512 KB).");
      return;
    }
    if (!/\.(json|abi|txt)$/i.test(file.name)) {
      setAbiStatus("invalid");
      setAbiError("Upload a .json ABI file.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result || "");
      setAbiText(text);
      void parseAbi(text);
    };
    reader.readAsText(file);
  };

  const toggleEvent = (name: string) => {
    setSelectedEvents((previous) =>
      previous.includes(name) ? previous.filter((n) => n !== name) : [...previous, name]
    );
  };

  const setFilter = (eventName: string, param: string, value: string) => {
    setTopicFilters((previous) => {
      const eventFilters = { ...(previous[eventName] || {}) };
      if (value.trim()) eventFilters[param] = value.trim();
      else delete eventFilters[param];
      const next = { ...previous, [eventName]: eventFilters };
      if (Object.keys(eventFilters).length === 0) delete next[eventName];
      return next;
    });
  };

  const onSubmit = async (values: FormValues) => {
    setError("");
    if (selectedEvents.length === 0) {
      setError("Select at least one event to monitor.");
      return;
    }
    const payload: Record<string, unknown> = {
      name: values.name,
      label: values.label || "",
      address: values.address,
      chain: values.chain,
      severity: values.severity,
      confirmations_override: values.confirmations_override ? Number(values.confirmations_override) : null,
      tags: (values.tags || "").split(",").map((t) => t.trim()).filter(Boolean),
      notes: values.notes || "",
      selected_events: selectedEvents,
      topic_filters: topicFilters,
    };
    if (abiText.trim()) payload.abi = abiText;

    try {
      const saved = monitor
        ? await contractMonitorService.update(monitor.id, payload)
        : await contractMonitorService.create(payload);
      router.push(`/app/monitors/contracts/${saved.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        const fields = err.fieldErrors();
        let assigned = false;
        for (const [key, message] of Object.entries(fields)) {
          if (key === "abi" || key === "selected_events" || key === "topic_filters") {
            setError(message);
            assigned = true;
          } else if (key in schema.shape) {
            setFieldError(key as keyof FormValues, { message });
            assigned = true;
          }
        }
        if (!assigned) setError(err.message);
      } else {
        setError("Saving failed. Try again.");
      }
    }
  };

  return (
    <form className="cs-card p-4" onSubmit={handleSubmit(onSubmit)} noValidate>
      {error && <div className="alert alert-danger py-2 small">{error}</div>}

      <div className="row g-3">
        <div className="col-md-6">
          <label className="form-label">Monitor name *</label>
          <input className={`form-control ${errors.name ? "is-invalid" : ""}`} placeholder="e.g. USDC transfers" {...register("name")} />
          {errors.name && <div className="invalid-feedback">{errors.name.message}</div>}
        </div>
        <div className="col-md-6">
          <label className="form-label">Contract label</label>
          <input className="form-control" placeholder="e.g. USDC (Sepolia)" {...register("label")} />
        </div>
        <div className="col-md-8">
          <label className="form-label">Contract address *</label>
          <input className={`form-control mono ${errors.address ? "is-invalid" : ""}`} placeholder="0x…" {...register("address")} disabled={!!monitor} />
          {errors.address && <div className="invalid-feedback">{errors.address.message}</div>}
        </div>
        <div className="col-md-4">
          <label className="form-label">Chain *</label>
          <select className={`form-select ${errors.chain ? "is-invalid" : ""}`} {...register("chain")} disabled={!!monitor}>
            <option value="">Select…</option>
            {chains.map((chain) => (
              <option key={chain.slug} value={chain.slug}>
                {chain.name} {chain.is_testnet ? "(testnet)" : ""}
              </option>
            ))}
          </select>
          {errors.chain && <div className="invalid-feedback">{errors.chain.message}</div>}
        </div>

        <div className="col-12">
          <label className="form-label d-flex justify-content-between">
            <span>Contract ABI (JSON) {monitor ? "" : "*"}</span>
            <label className="btn btn-outline-secondary btn-sm mb-0">
              Upload .json
              <input
                type="file"
                accept=".json,.abi,.txt,application/json"
                hidden
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) onAbiFile(file);
                }}
              />
            </label>
          </label>
          <textarea
            className={`form-control mono ${abiStatus === "invalid" ? "is-invalid" : ""}`}
            rows={7}
            placeholder={monitor ? "Paste a new ABI to replace the stored one (optional)" : '[{"type":"event","name":"Transfer",…}]'}
            value={abiText}
            onChange={(e) => setAbiText(e.target.value)}
            onBlur={() => void parseAbi(abiText)}
          />
          {abiStatus === "parsing" && <div className="form-hint mt-1">Validating ABI…</div>}
          {abiStatus === "invalid" && <div className="text-danger small mt-1">{abiError}</div>}
          {abiStatus === "valid" && abiEvents.length > 0 && (
            <div className="text-success small mt-1">✓ ABI valid — {abiEvents.length} event(s) found.</div>
          )}
          {monitor && !abiText && (
            <div className="form-hint mt-1">Using stored ABI “{monitor.abi_document?.name}”.</div>
          )}
        </div>

        {abiEvents.length > 0 && (
          <div className="col-12">
            <label className="form-label">Events to monitor *</label>
            <div className="d-grid gap-2">
              {abiEvents.map((event) => {
                const checked = selectedEvents.includes(event.name);
                const indexedInputs = event.inputs.filter((i) => i.indexed);
                return (
                  <div
                    key={event.signature}
                    className="cs-card p-3"
                    style={checked ? { borderColor: "var(--cs-accent)" } : undefined}
                  >
                    <label className="d-flex gap-2 align-items-start" style={{ cursor: "pointer" }}>
                      <input type="checkbox" className="form-check-input mt-1" checked={checked} onChange={() => toggleEvent(event.name)} />
                      <span>
                        <span className="fw-semibold small d-block">{event.name}</span>
                        <span className="mono form-hint d-block">{event.signature}</span>
                      </span>
                    </label>
                    {checked && indexedInputs.length > 0 && (
                      <div className="row g-2 mt-1 ms-4">
                        {indexedInputs.map((input) => (
                          <div className="col-md-6" key={input.name}>
                            <label className="form-label small mb-1">
                              Filter <code>{input.name || "(unnamed)"}</code> ({input.type})
                            </label>
                            <input
                              className="form-control form-control-sm mono"
                              placeholder="any value"
                              value={topicFilters[event.name]?.[input.name] || ""}
                              onChange={(e) => setFilter(event.name, input.name, e.target.value)}
                            />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="col-md-4">
          <label className="form-label">Severity</label>
          <select className="form-select" {...register("severity")}>
            {["info", "low", "medium", "high", "critical"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div className="col-md-4">
          <label className="form-label">Confirmations override</label>
          <input className="form-control" placeholder="chain default" inputMode="numeric" {...register("confirmations_override")} />
        </div>
        <div className="col-md-4">
          <label className="form-label">Tags</label>
          <input className="form-control" placeholder="defi, core" {...register("tags")} />
        </div>
        <div className="col-12">
          <label className="form-label">Notes</label>
          <input className="form-control" placeholder="internal context" {...register("notes")} />
        </div>
      </div>

      <div className="d-flex gap-2 mt-4">
        <button className="btn btn-primary px-4" disabled={isSubmitting}>
          {isSubmitting ? "Saving…" : monitor ? "Save changes" : "Create monitor"}
        </button>
        <button type="button" className="btn btn-outline-secondary" onClick={() => router.back()}>
          Cancel
        </button>
      </div>
    </form>
  );
}
