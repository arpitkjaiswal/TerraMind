export async function backendFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(`/api/backend/api/v1/${path.replace(/^\/+/, "")}`, { ...init, headers, cache: "no-store" });
  if (response.status === 204) return undefined as T;
  const payload = await response.json().catch(() => ({})) as { detail?: unknown };
  if (!response.ok) {
    const detail = typeof payload.detail === "string" ? payload.detail : response.status === 401 ? "Your session expired. Please sign in again." : `Request failed (${response.status}).`;
    throw new Error(detail);
  }
  return payload as T;
}

export async function authRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(`/api/auth/${path}`, { ...init, cache: "no-store", headers });
  const payload = await response.json().catch(() => ({})) as { detail?: unknown } & T;
  if (!response.ok) {
    const detail = typeof payload.detail === "string" ? payload.detail : `Authentication failed (${response.status}).`;
    throw new Error(detail);
  }
  return payload as T;
}
