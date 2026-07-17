"use client";

import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import CopyButton from "@/components/ui/CopyButton";
import EmptyState from "@/components/ui/EmptyState";
import { TableSkeleton } from "@/components/ui/Skeletons";
import { ApiError } from "@/lib/api";
import { confirmDialog, toast } from "@/lib/dialogs";
import { formatDate, timeAgo } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace-context";
import { workspaceService } from "@/services/workspaces";
import type { ApiKey } from "@/types";

export default function ApiKeysPage() {
  const { current, isOwner } = useWorkspace();
  const [keys, setKeys] = useState<ApiKey[] | null>(null);
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<string[]>(["read"]);
  const [createdKey, setCreatedKey] = useState<ApiKey | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!current) return;
    try {
      const page = await workspaceService.apiKeys();
      setKeys(page.results);
    } catch (err) {
      setKeys([]);
      if (err instanceof ApiError && err.status === 403) {
        setError("Only the workspace owner can manage API keys.");
      }
    }
  }, [current]);

  useEffect(() => {
    void load();
  }, [load]);

  const toggleScope = (scope: string) =>
    setScopes((s) => (s.includes(scope) ? s.filter((x) => x !== scope) : [...s, scope]));

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const key = await workspaceService.createApiKey({ name: name.trim(), scopes });
      setCreatedKey(key);
      setName("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Creation failed.");
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (key: ApiKey) => {
    const confirmed = await confirmDialog({
      title: `Revoke key “${key.name}”?`,
      text: `cs_${key.prefix}_… stops authenticating immediately. Integrations using it will fail.`,
      confirmText: "Revoke key",
      danger: true,
    });
    if (!confirmed) return;
    await workspaceService.revokeApiKey(key.id);
    toast("API key revoked");
    await load();
  };

  return (
    <div style={{ maxWidth: 860 }}>
      <PageHeader
        title="API keys"
        subtitle="Workspace-scoped keys for the REST API. Send them via the X-Api-Key header."
      />

      {error && <div className="alert alert-danger py-2 small">{error}</div>}

      {createdKey && (
        <div className="alert alert-warning small">
          <strong>Copy this key now — it will never be shown again:</strong>
          <div className="d-flex gap-2 mt-2">
            <input className="form-control form-control-sm mono" readOnly value={createdKey.key || ""} />
            <CopyButton value={createdKey.key || ""} />
            <button className="btn-close ms-1" aria-label="Dismiss" onClick={() => setCreatedKey(null)} />
          </div>
        </div>
      )}

      {isOwner && (
        <form className="cs-card p-3 mb-3 row g-2 align-items-end" onSubmit={create}>
          <div className="col-md-5">
            <label className="form-label small">Key name</label>
            <input
              className="form-control form-control-sm"
              placeholder="e.g. CI pipeline"
              required
              maxLength={100}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="col-md-4">
            <label className="form-label small d-block">Scopes</label>
            <div className="d-flex gap-3 pt-1">
              {["read", "write"].map((scope) => (
                <label className="form-check small mb-0" key={scope}>
                  <input
                    type="checkbox"
                    className="form-check-input"
                    checked={scopes.includes(scope)}
                    onChange={() => toggleScope(scope)}
                  />
                  <span className="form-check-label">{scope}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="col-md-3">
            <button className="btn btn-primary btn-sm w-100" disabled={busy || scopes.length === 0}>
              {busy ? "Creating…" : "Create key"}
            </button>
          </div>
          <div className="col-12 form-hint">
            <code>read</code> = list/query resources · <code>write</code> = create/update monitors, rules, webhooks.
          </div>
        </form>
      )}

      <div className="cs-card">
        {keys === null ? (
          <TableSkeleton rows={3} cols={5} />
        ) : keys.length === 0 ? (
          <EmptyState icon="🔑" title="No API keys" body="Create a key to integrate ChainSentinel with your own tooling." />
        ) : (
          <div className="table-scroll">
            <table className="table table-cs">
              <thead>
                <tr><th>Name</th><th>Key</th><th>Scopes</th><th>Created</th><th>Last used</th><th>Status</th><th></th></tr>
              </thead>
              <tbody>
                {keys.map((key) => (
                  <tr key={key.id}>
                    <td className="small fw-semibold">{key.name}</td>
                    <td><span className="address-chip">cs_{key.prefix}_…</span></td>
                    <td className="small">{key.scopes.join(", ")}</td>
                    <td className="small text-secondary">{formatDate(key.created_at)}</td>
                    <td className="small text-secondary">{timeAgo(key.last_used_at)}</td>
                    <td>
                      <span className={`badge-status ${key.is_valid ? "st-active" : "st-failed"}`}>
                        {key.is_valid ? "active" : "revoked"}
                      </span>
                    </td>
                    <td className="text-end">
                      {isOwner && key.is_valid && (
                        <button className="btn btn-outline-danger btn-sm" onClick={() => void revoke(key)}>
                          Revoke
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="cs-card p-3 mt-3">
        <h6 className="fw-semibold mb-2">Usage</h6>
        <pre className="code-block mb-0">
{`curl -H "X-Api-Key: cs_xxxxxxxx_..." \\
  "${typeof window !== "undefined" ? window.location.origin : ""}/api/v1/events/?page_size=10"`}
        </pre>
      </div>
    </div>
  );
}
