// Same-origin: the Start server proxies /api/* to the backend (see
// routes/api/$.ts). Nothing about the backend's address is in the client bundle.
const API_BASE = "/api";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly path: string,
    readonly body: string,
  ) {
    super(`API ${path} failed: ${status} ${body}`);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text();
    // The password gate is opt-in, so a 401 means it's on and we're not through
    // it. The auth endpoints are exempt: a failed login must surface its error
    // on the login page, not reload it out from under the user.
    const isAuthCall = path.startsWith("/auth/");
    if (res.status === 401 && !isAuthCall && typeof window !== "undefined") {
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.href = `/login?next=${next}`;
    }
    throw new ApiError(res.status, path, body);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/** JSON body helper: `apiFetch(path, json("POST", body))`. */
export function json(method: string, body?: unknown): RequestInit {
  return body === undefined ? { method } : { method, body: JSON.stringify(body) };
}
