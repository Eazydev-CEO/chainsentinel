import { api } from "@/lib/api";
import type { ApiKey, AuditLog, Invitation, Member, Paginated, Workspace } from "@/types";

export const workspaceService = {
  list: () => api.get<Paginated<Workspace> | Workspace[]>("/api/v1/workspaces/"),
  create: (name: string) => api.post<Workspace>("/api/v1/workspaces/", { name }),
  update: (id: number, name: string) => api.patch<Workspace>(`/api/v1/workspaces/${id}/`, { name }),
  remove: (id: number) => api.delete(`/api/v1/workspaces/${id}/`),
  invite: (id: number, email: string, role: string) =>
    api.post<Invitation>(`/api/v1/workspaces/${id}/invite/`, { email, role }),
  invitations: (id: number) => api.get<Invitation[]>(`/api/v1/workspaces/${id}/invitations/`),
  revokeInvitation: (id: number, invitationId: number) =>
    api.post(`/api/v1/workspaces/${id}/invitations/${invitationId}/revoke/`),
  acceptInvite: (token: string) =>
    api.post<Workspace>("/api/v1/workspaces/accept-invite/", { token }),

  members: (workspaceId: number) =>
    api.get<Paginated<Member>>("/api/v1/members/", { workspace: workspaceId, page_size: 100 }),
  updateMemberRole: (memberId: number, role: string) =>
    api.patch<Member>(`/api/v1/members/${memberId}/`, { role }),
  removeMember: (memberId: number) => api.delete(`/api/v1/members/${memberId}/`),

  apiKeys: () => api.get<Paginated<ApiKey>>("/api/v1/api-keys/"),
  createApiKey: (payload: { name: string; scopes: string[]; expires_at?: string | null }) =>
    api.post<ApiKey>("/api/v1/api-keys/", payload),
  revokeApiKey: (id: number) => api.delete<{ detail: string }>(`/api/v1/api-keys/${id}/`),

  auditLogs: (page = 1) => api.get<Paginated<AuditLog>>("/api/v1/audit-logs/", { page }),
};
