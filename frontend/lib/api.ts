/**
 * The single fetch layer for the Django REST API.
 *
 * - Same-origin requests (`/api/v1/...`) with `credentials: include` —
 *   auth lives in HttpOnly cookies, never in localStorage.
 * - CSRF token echoed from the `csrftoken` cookie on unsafe methods.
 * - The active workspace id rides along as `X-Workspace-Id`.
 * - On 401 it attempts one silent refresh, then replays the request.
 */

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "";

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;

  constructor(status: number, code: string, message: string, details: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }

  fieldErrors(): Record<string, string> {
    const out: Record<string, string> = {};
    if (this.details && typeof this.details === "object") {
      for (const [key, value] of Object.entries(this.details as Record<string, unknown>)) {
        if (Array.isArray(value)) out[key] = value.map(String).join(" ");
        else if (typeof value === "string") out[key] = value;
      }
    }
    return out;
  }
}

let workspaceIdProvider: () => number | null = () => null;

export function setWorkspaceIdProvider(fn: () => number | null): void {
  workspaceIdProvider = fn;
}

export function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

async function ensureCsrf(): Promise<string | null> {
  let token = getCookie("csrftoken");
  if (!token) {
    await fetch(`${BASE}/api/v1/auth/csrf/`, { credentials: "include" });
    token = getCookie("csrftoken");
  }
  return token;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  formData?: FormData;
  query?: Record<string, string | number | boolean | undefined | null>;
  skipWorkspace?: boolean;
  _retried?: boolean;
}

async function refreshSession(): Promise<boolean> {
  try {
    const token = await ensureCsrf();
    const response = await fetch(`${BASE}/api/v1/auth/refresh/`, {
      method: "POST",
      credentials: "include",
      headers: token ? { "X-CSRFToken": token } : {},
    });
    return response.ok;
  } catch {
    return false;
  }
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const headers: Record<string, string> = { Accept: "application/json" };

  let url = `${BASE}${path}`;
  if (options.query) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(options.query)) {
      if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
    }
    const qs = params.toString();
    if (qs) url += (url.includes("?") ? "&" : "?") + qs;
  }

  if (!options.skipWorkspace) {
    const workspaceId = workspaceIdProvider();
    if (workspaceId) headers["X-Workspace-Id"] = String(workspaceId);
  }

  let body: BodyInit | undefined;
  if (options.formData) {
    body = options.formData;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = await ensureCsrf();
    if (token) headers["X-CSRFToken"] = token;
  }

  const response = await fetch(url, { method, headers, body, credentials: "include" });

  if (response.status === 401 && !options._retried && !path.startsWith("/api/v1/auth/")) {
    const refreshed = await refreshSession();
    if (refreshed) return request<T>(path, { ...options, _retried: true });
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("cs:unauthorized"));
    }
  }

  if (response.status === 204) return null as T;

  let payload: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { detail: text.slice(0, 300) };
    }
  }

  if (!response.ok) {
    const envelope = (payload as { error?: { code?: string; message?: string; details?: unknown } })
      ?.error;
    throw new ApiError(
      response.status,
      envelope?.code || "error",
      envelope?.message || `Request failed (${response.status})`,
      envelope?.details ?? payload
    );
  }
  return payload as T;
}

export const api = {
  get: <T>(path: string, query?: RequestOptions["query"]) => request<T>(path, { query }),
  post: <T>(path: string, body?: unknown, query?: RequestOptions["query"]) =>
    request<T>(path, { method: "POST", body, query }),
  postForm: <T>(path: string, formData: FormData, query?: RequestOptions["query"]) =>
    request<T>(path, { method: "POST", formData, query }),
  patch: <T>(path: string, body?: unknown, query?: RequestOptions["query"]) =>
    request<T>(path, { method: "PATCH", body, query }),
  put: <T>(path: string, body?: unknown, query?: RequestOptions["query"]) =>
    request<T>(path, { method: "PUT", body, query }),
  delete: <T>(path: string, query?: RequestOptions["query"]) =>
    request<T>(path, { method: "DELETE", query }),
};
