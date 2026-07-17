"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ApiError } from "@/lib/api";
import { chainService } from "@/services/platform";
import { walletMonitorService } from "@/services/monitors";
import type { Chain, WalletMonitor } from "@/types";

const ADDRESS_RE = /^0x[0-9a-fA-F]{40}$/;
const WEI_RE = /^\d+$/;

const schema = z.object({
  name: z.string().min(1, "Give the monitor a name").max(120),
  address: z.string().regex(ADDRESS_RE, "Must be a 0x-prefixed 40-hex-char address"),
  chain: z.string().min(1, "Pick a chain"),
  direction: z.enum(["incoming", "outgoing", "both"]),
  event_types: z.array(z.string()).min(1, "Select at least one event category"),
  token_contract: z.string().regex(ADDRESS_RE, "Invalid contract address").or(z.literal("")),
  min_value_wei: z.string().regex(WEI_RE, "Raw integer (wei) only").or(z.literal("")),
  large_tx_threshold_wei: z.string().regex(WEI_RE, "Raw integer (wei) only").or(z.literal("")),
  confirmations_override: z.string().regex(/^\d*$/, "Whole number").optional().or(z.literal("")),
  severity: z.enum(["info", "low", "medium", "high", "critical"]),
  tags: z.string().max(400).optional().or(z.literal("")),
  notes: z.string().max(2000).optional().or(z.literal("")),
});

type FormValues = z.infer<typeof schema>;

const CATEGORIES = [
  { value: "native_transfer", label: "Native transfers", hint: "ETH/BNB/POL sent or received" },
  { value: "erc20_transfer", label: "ERC-20 transfers", hint: "Token movements" },
  { value: "nft_transfer", label: "NFT transfers", hint: "ERC-721 with token IDs" },
  { value: "approval", label: "Approvals", hint: "Created / changed / revoked / operator" },
];

export default function WalletMonitorForm({ monitor }: { monitor?: WalletMonitor }) {
  const router = useRouter();
  const [chains, setChains] = useState<Chain[]>([]);
  const [error, setError] = useState("");
  const {
    register,
    handleSubmit,
    setError: setFieldError,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: monitor
      ? {
          name: monitor.name,
          address: monitor.address,
          chain: monitor.chain,
          direction: monitor.direction,
          event_types: monitor.event_types,
          token_contract: monitor.token_contract || "",
          min_value_wei: monitor.min_value_wei || "",
          large_tx_threshold_wei: monitor.large_tx_threshold_wei || "",
          confirmations_override: monitor.confirmations_override?.toString() || "",
          severity: monitor.severity,
          tags: (monitor.tags || []).join(", "),
          notes: monitor.notes || "",
        }
      : {
          direction: "both",
          severity: "medium",
          event_types: ["native_transfer", "erc20_transfer"],
          token_contract: "",
          min_value_wei: "",
          large_tx_threshold_wei: "",
          tags: "",
          notes: "",
        },
  });

  useEffect(() => {
    chainService.list().then((all) => setChains(all.filter((c) => c.is_active))).catch(() => setChains([]));
  }, []);

  const selectedTypes = watch("event_types") || [];

  const toggleType = (value: string) => {
    const next = selectedTypes.includes(value)
      ? selectedTypes.filter((t) => t !== value)
      : [...selectedTypes, value];
    setValue("event_types", next, { shouldValidate: true });
  };

  const onSubmit = async (values: FormValues) => {
    setError("");
    const payload = {
      name: values.name,
      address: values.address,
      chain: values.chain,
      direction: values.direction,
      event_types: values.event_types,
      token_contract: values.token_contract || "",
      min_value_wei: values.min_value_wei || null,
      large_tx_threshold_wei: values.large_tx_threshold_wei || null,
      confirmations_override: values.confirmations_override ? Number(values.confirmations_override) : null,
      severity: values.severity,
      tags: (values.tags || "").split(",").map((t) => t.trim()).filter(Boolean),
      notes: values.notes || "",
    } as Partial<WalletMonitor>;

    try {
      const saved = monitor
        ? await walletMonitorService.update(monitor.id, payload)
        : await walletMonitorService.create(payload);
      router.push(`/app/monitors/wallets/${saved.id}`);
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
          <input className={`form-control ${errors.name ? "is-invalid" : ""}`} placeholder="e.g. Treasury multisig" {...register("name")} />
          {errors.name && <div className="invalid-feedback">{errors.name.message}</div>}
        </div>
        <div className="col-md-6">
          <label className="form-label">Chain *</label>
          <select className={`form-select ${errors.chain ? "is-invalid" : ""}`} {...register("chain")} disabled={!!monitor}>
            <option value="">Select a chain…</option>
            {chains.map((chain) => (
              <option key={chain.slug} value={chain.slug}>
                {chain.name} {chain.is_testnet ? "(testnet)" : ""}
              </option>
            ))}
          </select>
          {errors.chain && <div className="invalid-feedback">{errors.chain.message}</div>}
          {chains.length === 0 && (
            <div className="form-hint mt-1">No active chains — run the seed command or activate chains in admin.</div>
          )}
        </div>

        <div className="col-12">
          <label className="form-label">Wallet address *</label>
          <input
            className={`form-control mono ${errors.address ? "is-invalid" : ""}`}
            placeholder="0x…"
            {...register("address")}
            disabled={!!monitor}
          />
          {errors.address && <div className="invalid-feedback">{errors.address.message}</div>}
          <div className="form-hint mt-1">Validated and stored in EIP-55 checksum form.</div>
        </div>

        <div className="col-md-6">
          <label className="form-label">Direction</label>
          <select className="form-select" {...register("direction")}>
            <option value="both">Both directions</option>
            <option value="incoming">Incoming only</option>
            <option value="outgoing">Outgoing only</option>
          </select>
        </div>
        <div className="col-md-6">
          <label className="form-label">Severity</label>
          <select className="form-select" {...register("severity")}>
            {["info", "low", "medium", "high", "critical"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        <div className="col-12">
          <label className="form-label d-block">Event categories *</label>
          <div className="row g-2">
            {CATEGORIES.map((category) => (
              <div className="col-md-6" key={category.value}>
                <label
                  className={`cs-card d-flex gap-2 p-3 align-items-start w-100 ${selectedTypes.includes(category.value) ? "border-primary" : ""}`}
                  style={{ cursor: "pointer", borderColor: selectedTypes.includes(category.value) ? "var(--cs-accent)" : undefined }}
                >
                  <input
                    type="checkbox"
                    className="form-check-input mt-1"
                    checked={selectedTypes.includes(category.value)}
                    onChange={() => toggleType(category.value)}
                  />
                  <span>
                    <span className="d-block fw-semibold small">{category.label}</span>
                    <span className="d-block form-hint">{category.hint}</span>
                  </span>
                </label>
              </div>
            ))}
          </div>
          {errors.event_types && <div className="text-danger small mt-1">{errors.event_types.message}</div>}
        </div>

        <div className="col-md-6">
          <label className="form-label">Token contract filter (optional)</label>
          <input className={`form-control mono ${errors.token_contract ? "is-invalid" : ""}`} placeholder="0x… (only this token)" {...register("token_contract")} />
          {errors.token_contract && <div className="invalid-feedback">{errors.token_contract.message}</div>}
        </div>
        <div className="col-md-6">
          <label className="form-label">Confirmations override (optional)</label>
          <input className="form-control" placeholder="chain default" inputMode="numeric" {...register("confirmations_override")} />
        </div>

        <div className="col-md-6">
          <label className="form-label">Minimum value (wei / base units)</label>
          <input className={`form-control mono ${errors.min_value_wei ? "is-invalid" : ""}`} placeholder="e.g. 1000000000000000000 = 1 ETH" {...register("min_value_wei")} />
          {errors.min_value_wei && <div className="invalid-feedback">{errors.min_value_wei.message}</div>}
          <div className="form-hint mt-1">Transfers below this raw value are ignored.</div>
        </div>
        <div className="col-md-6">
          <label className="form-label">Large-transfer threshold (wei)</label>
          <input className={`form-control mono ${errors.large_tx_threshold_wei ? "is-invalid" : ""}`} placeholder="flag + escalate at/above this value" {...register("large_tx_threshold_wei")} />
          {errors.large_tx_threshold_wei && <div className="invalid-feedback">{errors.large_tx_threshold_wei.message}</div>}
        </div>

        <div className="col-md-6">
          <label className="form-label">Tags</label>
          <input className="form-control" placeholder="treasury, ops (comma separated)" {...register("tags")} />
        </div>
        <div className="col-md-6">
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
