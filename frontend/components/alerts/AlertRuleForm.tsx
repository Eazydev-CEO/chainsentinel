"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ApiError } from "@/lib/api";
import { eventTypeLabel } from "@/lib/format";
import { contractMonitorService, walletMonitorService } from "@/services/monitors";
import { alertRuleService, chainService, webhookService } from "@/services/platform";
import type { AlertRule, Chain, ContractMonitor, WalletMonitor, WebhookEndpoint } from "@/types";

const ADDRESS_RE = /^0x[0-9a-fA-F]{40}$/;
const WEI_RE = /^\d+$/;

const schema = z.object({
  name: z.string().min(1, "Name the rule").max(120),
  description: z.string().max(1000).optional().or(z.literal("")),
  wallet_monitor: z.string().optional().or(z.literal("")),
  contract_monitor: z.string().optional().or(z.literal("")),
  chain: z.string().optional().or(z.literal("")),
  event_types: z.array(z.string()),
  token_address: z.string().regex(ADDRESS_RE).or(z.literal("")),
  min_amount_wei: z.string().regex(WEI_RE, "Raw integer only").or(z.literal("")),
  max_amount_wei: z.string().regex(WEI_RE, "Raw integer only").or(z.literal("")),
  from_address: z.string().regex(ADDRESS_RE).or(z.literal("")),
  to_address: z.string().regex(ADDRESS_RE).or(z.literal("")),
  spender_address: z.string().regex(ADDRESS_RE).or(z.literal("")),
  trigger_on: z.enum(["confirmed", "reverted"]),
  severity: z.enum(["", "info", "low", "medium", "high", "critical"]),
  cooldown_seconds: z.string().regex(/^\d*$/),
  group_window_seconds: z.string().regex(/^\d*$/),
  notify_in_app: z.boolean(),
  notify_email: z.boolean(),
  notify_webhook: z.boolean(),
  webhook: z.string().optional().or(z.literal("")),
});

type FormValues = z.infer<typeof schema>;

const EVENT_TYPES = [
  "native_received", "native_sent", "erc20_received", "erc20_sent", "nft_received", "nft_sent",
  "approval_created", "approval_changed", "approval_revoked", "approval_for_all",
  "contract_event", "large_transfer",
];

export default function AlertRuleForm({ rule }: { rule?: AlertRule }) {
  const router = useRouter();
  const [chains, setChains] = useState<Chain[]>([]);
  const [walletMonitors, setWalletMonitors] = useState<WalletMonitor[]>([]);
  const [contractMonitors, setContractMonitors] = useState<ContractMonitor[]>([]);
  const [webhooks, setWebhooks] = useState<WebhookEndpoint[]>([]);
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
    defaultValues: rule
      ? {
          name: rule.name,
          description: rule.description || "",
          wallet_monitor: rule.wallet_monitor?.toString() || "",
          contract_monitor: rule.contract_monitor?.toString() || "",
          chain: rule.chain || "",
          event_types: rule.event_types || [],
          token_address: rule.token_address || "",
          min_amount_wei: rule.min_amount_wei || "",
          max_amount_wei: rule.max_amount_wei || "",
          from_address: rule.from_address || "",
          to_address: rule.to_address || "",
          spender_address: rule.spender_address || "",
          trigger_on: rule.trigger_on,
          severity: (rule.severity || "") as FormValues["severity"],
          cooldown_seconds: String(rule.cooldown_seconds || ""),
          group_window_seconds: String(rule.group_window_seconds || ""),
          notify_in_app: rule.notify_in_app,
          notify_email: rule.notify_email,
          notify_webhook: rule.notify_webhook,
          webhook: rule.webhook?.toString() || "",
        }
      : {
          event_types: [],
          trigger_on: "confirmed",
          severity: "",
          notify_in_app: true,
          notify_email: false,
          notify_webhook: false,
          token_address: "", min_amount_wei: "", max_amount_wei: "",
          from_address: "", to_address: "", spender_address: "",
          cooldown_seconds: "", group_window_seconds: "",
          description: "", wallet_monitor: "", contract_monitor: "", chain: "", webhook: "",
        },
  });

  useEffect(() => {
    chainService.list().then(setChains).catch(() => setChains([]));
    walletMonitorService.list({ page_size: 100 }).then((p) => setWalletMonitors(p.results)).catch(() => {});
    contractMonitorService.list({ page_size: 100 }).then((p) => setContractMonitors(p.results)).catch(() => {});
    webhookService.list({ page_size: 100 }).then((p) => setWebhooks(p.results)).catch(() => {});
  }, []);

  const selectedTypes = watch("event_types");
  const notifyWebhook = watch("notify_webhook");

  const toggleType = (type: string) => {
    const next = selectedTypes.includes(type)
      ? selectedTypes.filter((t) => t !== type)
      : [...selectedTypes, type];
    setValue("event_types", next);
  };

  const onSubmit = async (values: FormValues) => {
    setError("");
    const payload: Record<string, unknown> = {
      name: values.name,
      description: values.description || "",
      wallet_monitor: values.wallet_monitor ? Number(values.wallet_monitor) : null,
      contract_monitor: values.contract_monitor ? Number(values.contract_monitor) : null,
      chain: values.chain || null,
      event_types: values.event_types,
      token_address: values.token_address,
      min_amount_wei: values.min_amount_wei || null,
      max_amount_wei: values.max_amount_wei || null,
      from_address: values.from_address,
      to_address: values.to_address,
      spender_address: values.spender_address,
      trigger_on: values.trigger_on,
      severity: values.severity,
      cooldown_seconds: values.cooldown_seconds ? Number(values.cooldown_seconds) : 0,
      group_window_seconds: values.group_window_seconds ? Number(values.group_window_seconds) : 0,
      notify_in_app: values.notify_in_app,
      notify_email: values.notify_email,
      notify_webhook: values.notify_webhook,
      webhook: values.webhook ? Number(values.webhook) : null,
    };
    try {
      if (rule) await alertRuleService.update(rule.id, payload);
      else await alertRuleService.create(payload);
      router.push("/app/alert-rules");
    } catch (err) {
      if (err instanceof ApiError) {
        const fields = err.fieldErrors();
        let assigned = false;
        for (const [key, message] of Object.entries(fields)) {
          if (key in schema.shape) {
            setFieldError(key as keyof FormValues, { message });
            assigned = true;
          }
        }
        if (!assigned) setError(err.message);
      } else {
        setError("Saving failed.");
      }
    }
  };

  return (
    <form className="cs-card p-4" onSubmit={handleSubmit(onSubmit)} noValidate>
      {error && <div className="alert alert-danger py-2 small">{error}</div>}

      <h6 className="fw-semibold mb-3">Rule</h6>
      <div className="row g-3 mb-4">
        <div className="col-md-6">
          <label className="form-label">Name *</label>
          <input className={`form-control ${errors.name ? "is-invalid" : ""}`} {...register("name")} />
          {errors.name && <div className="invalid-feedback">{errors.name.message}</div>}
        </div>
        <div className="col-md-6">
          <label className="form-label">Description</label>
          <input className="form-control" {...register("description")} />
        </div>
      </div>

      <h6 className="fw-semibold mb-3">Match filters <span className="form-hint fw-normal">(empty = match anything)</span></h6>
      <div className="row g-3 mb-2">
        <div className="col-md-4">
          <label className="form-label">Wallet monitor</label>
          <select className="form-select" {...register("wallet_monitor")}>
            <option value="">Any</option>
            {walletMonitors.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </div>
        <div className="col-md-4">
          <label className="form-label">Contract monitor</label>
          <select className="form-select" {...register("contract_monitor")}>
            <option value="">Any</option>
            {contractMonitors.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </div>
        <div className="col-md-4">
          <label className="form-label">Chain</label>
          <select className="form-select" {...register("chain")}>
            <option value="">Any</option>
            {chains.map((chain) => <option key={chain.slug} value={chain.slug}>{chain.name}</option>)}
          </select>
        </div>

        <div className="col-12">
          <label className="form-label d-block">Event types</label>
          <div className="d-flex flex-wrap gap-2">
            {EVENT_TYPES.map((type) => (
              <button
                type="button"
                key={type}
                className={`btn btn-sm ${selectedTypes.includes(type) ? "btn-primary" : "btn-outline-secondary"}`}
                onClick={() => toggleType(type)}
              >
                {eventTypeLabel(type)}
              </button>
            ))}
          </div>
          <div className="form-hint mt-1">None selected = all event types match.</div>
        </div>

        <div className="col-md-4">
          <label className="form-label">Token contract</label>
          <input className={`form-control mono ${errors.token_address ? "is-invalid" : ""}`} placeholder="0x…" {...register("token_address")} />
        </div>
        <div className="col-md-4">
          <label className="form-label">Min amount (wei)</label>
          <input className={`form-control mono ${errors.min_amount_wei ? "is-invalid" : ""}`} {...register("min_amount_wei")} />
        </div>
        <div className="col-md-4">
          <label className="form-label">Max amount (wei)</label>
          <input className={`form-control mono ${errors.max_amount_wei ? "is-invalid" : ""}`} {...register("max_amount_wei")} />
        </div>
        <div className="col-md-4">
          <label className="form-label">Sender address</label>
          <input className={`form-control mono ${errors.from_address ? "is-invalid" : ""}`} placeholder="0x…" {...register("from_address")} />
        </div>
        <div className="col-md-4">
          <label className="form-label">Receiver address</label>
          <input className={`form-control mono ${errors.to_address ? "is-invalid" : ""}`} placeholder="0x…" {...register("to_address")} />
        </div>
        <div className="col-md-4">
          <label className="form-label">Spender address</label>
          <input className={`form-control mono ${errors.spender_address ? "is-invalid" : ""}`} placeholder="0x…" {...register("spender_address")} />
        </div>
        <div className="col-md-4">
          <label className="form-label">Trigger on</label>
          <select className="form-select" {...register("trigger_on")}>
            <option value="confirmed">Confirmed events</option>
            <option value="reverted">Reverted events (reorg watch)</option>
          </select>
        </div>
      </div>

      <h6 className="fw-semibold mb-3 mt-3">Behaviour</h6>
      <div className="row g-3 mb-2">
        <div className="col-md-4">
          <label className="form-label">Alert severity</label>
          <select className="form-select" {...register("severity")}>
            <option value="">Inherit from event</option>
            {["info", "low", "medium", "high", "critical"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div className="col-md-4">
          <label className="form-label">Cooldown (seconds)</label>
          <input className="form-control" placeholder="0 = no cooldown" inputMode="numeric" {...register("cooldown_seconds")} />
          <div className="form-hint mt-1">Suppress repeat alerts for the same fingerprint.</div>
        </div>
        <div className="col-md-4">
          <label className="form-label">Grouping window (seconds)</label>
          <input className="form-control" placeholder="0 = no grouping" inputMode="numeric" {...register("group_window_seconds")} />
          <div className="form-hint mt-1">Fold repeats into one alert with a counter (debounce).</div>
        </div>
      </div>

      <h6 className="fw-semibold mb-3 mt-3">Actions</h6>
      <div className="d-grid gap-2 mb-3">
        <label className="form-check">
          <input type="checkbox" className="form-check-input" {...register("notify_in_app")} />
          <span className="form-check-label small">In-app notification to workspace members</span>
        </label>
        <label className="form-check">
          <input type="checkbox" className="form-check-input" {...register("notify_email")} />
          <span className="form-check-label small">Email members (respects their severity preferences)</span>
        </label>
        <label className="form-check">
          <input type="checkbox" className="form-check-input" {...register("notify_webhook")} />
          <span className="form-check-label small">Deliver to webhook</span>
        </label>
        {notifyWebhook && (
          <div className="ms-4" style={{ maxWidth: 420 }}>
            <select className="form-select form-select-sm" {...register("webhook")}>
              <option value="">All endpoints subscribed to alert.triggered</option>
              {webhooks.map((endpoint) => (
                <option key={endpoint.id} value={endpoint.id}>{endpoint.name}</option>
              ))}
            </select>
          </div>
        )}
        <label className="form-check">
          <input type="checkbox" className="form-check-input" disabled />
          <span className="form-check-label small text-secondary">Telegram — coming soon</span>
        </label>
        <label className="form-check">
          <input type="checkbox" className="form-check-input" disabled />
          <span className="form-check-label small text-secondary">Slack — coming soon</span>
        </label>
      </div>

      <div className="d-flex gap-2 mt-3">
        <button className="btn btn-primary px-4" disabled={isSubmitting}>
          {isSubmitting ? "Saving…" : rule ? "Save rule" : "Create rule"}
        </button>
        <button type="button" className="btn btn-outline-secondary" onClick={() => router.back()}>
          Cancel
        </button>
      </div>
    </form>
  );
}
