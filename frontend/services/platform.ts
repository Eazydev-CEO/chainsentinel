import { api } from "@/lib/api";
import type {
  Alert,
  AlertDetail,
  AlertNote,
  AlertRule,
  AnalyticsCharts,
  AnalyticsOverview,
  BlockchainEvent,
  BlockchainEventDetail,
  Chain,
  Notification,
  NotificationPrefs,
  Paginated,
  ProviderHealth,
  WebhookDelivery,
  WebhookEndpoint,
} from "@/types";

type Query = Record<string, string | number | boolean | undefined | null>;

export const chainService = {
  list: () => api.get<Chain[]>("/api/v1/chains/"),
  providerHealth: () => api.get<ProviderHealth[]>("/api/v1/provider-health/"),
};

export const eventService = {
  list: (query?: Query) => api.get<Paginated<BlockchainEvent>>("/api/v1/events/", query),
  get: (id: number) => api.get<BlockchainEventDetail>(`/api/v1/events/${id}/`),
};

export const alertService = {
  list: (query?: Query) => api.get<Paginated<Alert>>("/api/v1/alerts/", query),
  get: (id: number) => api.get<AlertDetail>(`/api/v1/alerts/${id}/`),
  acknowledge: (id: number) => api.post<Alert>(`/api/v1/alerts/${id}/acknowledge/`),
  resolve: (id: number) => api.post<Alert>(`/api/v1/alerts/${id}/resolve/`),
  addNote: (id: number, body: string) => api.post<AlertNote>(`/api/v1/alerts/${id}/notes/`, { body }),
};

export const alertRuleService = {
  list: (query?: Query) => api.get<Paginated<AlertRule>>("/api/v1/alert-rules/", query),
  get: (id: number) => api.get<AlertRule>(`/api/v1/alert-rules/${id}/`),
  create: (payload: Record<string, unknown>) => api.post<AlertRule>("/api/v1/alert-rules/", payload),
  update: (id: number, payload: Record<string, unknown>) =>
    api.patch<AlertRule>(`/api/v1/alert-rules/${id}/`, payload),
  remove: (id: number) => api.delete(`/api/v1/alert-rules/${id}/`),
};

export const webhookService = {
  list: (query?: Query) => api.get<Paginated<WebhookEndpoint>>("/api/v1/webhooks/", query),
  get: (id: number) => api.get<WebhookEndpoint>(`/api/v1/webhooks/${id}/`),
  create: (payload: Record<string, unknown>) => api.post<WebhookEndpoint>("/api/v1/webhooks/", payload),
  update: (id: number, payload: Record<string, unknown>) =>
    api.patch<WebhookEndpoint>(`/api/v1/webhooks/${id}/`, payload),
  remove: (id: number) => api.delete(`/api/v1/webhooks/${id}/`),
  regenerateSecret: (id: number) =>
    api.post<WebhookEndpoint>(`/api/v1/webhooks/${id}/regenerate-secret/`),
  test: (id: number) => api.post<WebhookDelivery>(`/api/v1/webhooks/${id}/test/`),
  deliveries: (query?: Query) =>
    api.get<Paginated<WebhookDelivery>>("/api/v1/webhook-deliveries/", query),
  replay: (deliveryId: number) =>
    api.post<WebhookDelivery>(`/api/v1/webhook-deliveries/${deliveryId}/replay/`),
};

export const notificationService = {
  list: (query?: Query) => api.get<Paginated<Notification>>("/api/v1/notifications/", query),
  unreadCount: () => api.get<{ unread: number }>("/api/v1/notifications/unread-count/"),
  markRead: (id: number) => api.post<Notification>(`/api/v1/notifications/${id}/read/`),
  markAllRead: () => api.post<{ marked_read: number }>("/api/v1/notifications/mark-all-read/"),
  preferences: () => api.get<NotificationPrefs>("/api/v1/notifications/preferences/"),
  updatePreferences: (prefs: Partial<NotificationPrefs>) =>
    api.put<NotificationPrefs>("/api/v1/notifications/preferences/", prefs),
};

export const analyticsService = {
  overview: () => api.get<AnalyticsOverview>("/api/v1/analytics/overview/"),
  charts: (days = 14) => api.get<AnalyticsCharts>("/api/v1/analytics/charts/", { days }),
};

export const contactService = {
  send: (payload: { name: string; email: string; subject: string; message: string }) =>
    api.post<{ detail: string }>("/api/v1/contact/", payload),
};
