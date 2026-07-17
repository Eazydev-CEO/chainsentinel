"use client";

import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/app/PageHeader";
import EmptyState from "@/components/ui/EmptyState";
import { TableSkeleton } from "@/components/ui/Skeletons";
import { ApiError } from "@/lib/api";
import { confirmDialog, toast } from "@/lib/dialogs";
import { formatDate } from "@/lib/format";
import { useAuth } from "@/lib/auth-context";
import { useWorkspace } from "@/lib/workspace-context";
import { workspaceService } from "@/services/workspaces";
import type { Invitation, Member } from "@/types";

const ROLES = ["admin", "analyst", "viewer"] as const;

const ROLE_HELP: Record<string, string> = {
  owner: "Full control incl. billing, API keys, deletion",
  admin: "Manage monitors, rules, webhooks, analysts & viewers",
  analyst: "View everything, acknowledge alerts, add notes",
  viewer: "Read-only dashboard access",
};

export default function MembersSettingsPage() {
  const { current, canWrite, isOwner } = useWorkspace();
  const { user } = useAuth();
  const [members, setMembers] = useState<Member[] | null>(null);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<(typeof ROLES)[number]>("viewer");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!current) return;
    try {
      const page = await workspaceService.members(current.id);
      setMembers(page.results);
      if (canWrite) {
        setInvitations(await workspaceService.invitations(current.id));
      }
    } catch {
      setMembers([]);
    }
  }, [current, canWrite]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!current) return null;

  const invite = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    try {
      await workspaceService.invite(current.id, email.trim(), role);
      setNotice(`Invitation sent to ${email.trim()}.`);
      setEmail("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Invite failed.");
    } finally {
      setBusy(false);
    }
  };

  const changeRole = async (member: Member, newRole: string) => {
    setError("");
    try {
      await workspaceService.updateMemberRole(member.id, newRole);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Role change failed.");
    }
  };

  const remove = async (member: Member) => {
    const isSelf = member.user_id === user?.id;
    const confirmed = await confirmDialog({
      title: isSelf ? "Leave this workspace?" : `Remove ${member.email}?`,
      text: isSelf
        ? "You lose access immediately. An owner or admin can invite you back."
        : "They lose access to every monitor, alert and webhook in this workspace.",
      confirmText: isSelf ? "Leave workspace" : "Remove member",
      danger: true,
    });
    if (!confirmed) return;
    try {
      await workspaceService.removeMember(member.id);
      toast(isSelf ? "You left the workspace" : "Member removed");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Removal failed.");
    }
  };

  return (
    <div style={{ maxWidth: 860 }}>
      <PageHeader title="Members" subtitle={`People with access to ${current.name}.`} />

      {error && <div className="alert alert-danger py-2 small">{error}</div>}
      {notice && <div className="alert alert-success py-2 small">{notice}</div>}

      {canWrite && (
        <form className="cs-card p-3 mb-3 row g-2 align-items-end" onSubmit={invite}>
          <div className="col-md-6">
            <label className="form-label small">Invite by email</label>
            <input
              type="email"
              required
              className="form-control form-control-sm"
              placeholder="teammate@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="col-md-3">
            <label className="form-label small">Role</label>
            <select className="form-select form-select-sm" value={role} onChange={(e) => setRole(e.target.value as (typeof ROLES)[number])}>
              {ROLES.filter((r) => (isOwner ? true : r !== "admin")).map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>
          <div className="col-md-3">
            <button className="btn btn-primary btn-sm w-100" disabled={busy}>
              {busy ? "Sending…" : "Send invitation"}
            </button>
          </div>
          <div className="col-12 form-hint">{ROLE_HELP[role]}</div>
        </form>
      )}

      <div className="cs-card mb-3">
        {members === null ? (
          <TableSkeleton rows={4} cols={4} />
        ) : (
          <div className="table-scroll">
            <table className="table table-cs">
              <thead>
                <tr><th>Member</th><th>Role</th><th>Joined</th><th></th></tr>
              </thead>
              <tbody>
                {members.map((member) => (
                  <tr key={member.id}>
                    <td>
                      <span className="fw-semibold small">{member.name || member.email}</span>
                      <div className="small text-secondary">{member.email}</div>
                    </td>
                    <td>
                      {member.role === "owner" || !canWrite ? (
                        <span className="badge-status st-active text-capitalize">{member.role}</span>
                      ) : (
                        <select
                          className="form-select form-select-sm"
                          style={{ width: 130 }}
                          value={member.role}
                          onChange={(e) => void changeRole(member, e.target.value)}
                        >
                          {ROLES.map((r) => (
                            <option key={r} value={r}>{r}</option>
                          ))}
                        </select>
                      )}
                    </td>
                    <td className="small text-secondary">{formatDate(member.joined_at)}</td>
                    <td className="text-end">
                      {member.role !== "owner" && (canWrite || member.user_id === user?.id) && (
                        <button className="btn btn-outline-danger btn-sm" onClick={() => void remove(member)}>
                          {member.user_id === user?.id ? "Leave" : "Remove"}
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

      {canWrite && (
        <div className="cs-card">
          <div className="p-3 pb-2">
            <h6 className="fw-semibold mb-0">Pending invitations</h6>
          </div>
          {invitations.length === 0 ? (
            <EmptyState icon="✉" title="No pending invitations" />
          ) : (
            <div className="table-scroll">
              <table className="table table-cs">
                <thead>
                  <tr><th>Email</th><th>Role</th><th>Invited by</th><th>Expires</th><th></th></tr>
                </thead>
                <tbody>
                  {invitations.map((invitation) => (
                    <tr key={invitation.id}>
                      <td className="small">{invitation.email}</td>
                      <td className="small text-capitalize">{invitation.role}</td>
                      <td className="small text-secondary">{invitation.invited_by_email || "—"}</td>
                      <td className="small text-secondary">{formatDate(invitation.expires_at)}</td>
                      <td className="text-end">
                        <button
                          className="btn btn-outline-danger btn-sm"
                          onClick={async () => {
                            await workspaceService.revokeInvitation(current.id, invitation.id);
                            await load();
                          }}
                        >
                          Revoke
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
