import { api } from "@/lib/api";
import type { User, UserSession } from "@/types";

export const authService = {
  me: () => api.get<User>("/api/v1/auth/me/"),
  updateProfile: (payload: Partial<User> & { profile?: Partial<User["profile"]> }) =>
    api.patch<User>("/api/v1/auth/me/", payload),
  verifyEmail: (token: string) => api.post<{ detail: string }>("/api/v1/auth/verify-email/", { token }),
  resendVerification: () => api.post<{ detail: string }>("/api/v1/auth/resend-verification/"),
  forgotPassword: (email: string) =>
    api.post<{ detail: string }>("/api/v1/auth/password/forgot/", { email }),
  resetPassword: (token: string, password: string) =>
    api.post<{ detail: string }>("/api/v1/auth/password/reset/", { token, password }),
  changePassword: (current_password: string, new_password: string) =>
    api.post<{ detail: string }>("/api/v1/auth/password/change/", { current_password, new_password }),
  sessions: () => api.get<UserSession[]>("/api/v1/auth/sessions/"),
  revokeSession: (id: number) => api.delete<{ detail: string }>(`/api/v1/auth/sessions/${id}/`),
  revokeOtherSessions: () => api.post<{ detail: string }>("/api/v1/auth/sessions/revoke-others/"),
};
