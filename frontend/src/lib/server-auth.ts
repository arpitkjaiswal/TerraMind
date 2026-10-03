import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

export const ACCESS_COOKIE = "aegis_access";
export const REFRESH_COOKIE = "aegis_refresh";
export const ACCESS_SECONDS = 60 * 60;
export const REFRESH_SECONDS = 60 * 60 * 24 * 7;
export interface TokenPair { access_token: string; refresh_token: string; expires_in: number }

export function backendUrl() {
  const value = process.env.BACKEND_URL?.trim().replace(/\/$/, "");
  if (!value) throw new Error("Authentication service is not configured.");
  const url = new URL(value);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error("Invalid backend configuration.");
  if (process.env.NODE_ENV === 'production' && url.protocol !== 'https:' && !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) throw new Error("Backend must use HTTPS.");
  return value;
}

export async function upstreamFetch(url: string, init: RequestInit = {}) {
  return fetch(url, { ...init, cache: "no-store", redirect: "manual", signal: AbortSignal.timeout(30000) });
}

export async function getTokens() {
  const jar = await cookies();
  return { access: jar.get(ACCESS_COOKIE)?.value, refresh: jar.get(REFRESH_COOKIE)?.value };
}

export function parseTokenPair(value: unknown): TokenPair {
  const pair = value as Partial<TokenPair> | null;
  if (!pair || typeof pair.access_token !== 'string' || !pair.access_token || typeof pair.refresh_token !== 'string' || !pair.refresh_token || typeof pair.expires_in !== 'number' || !Number.isFinite(pair.expires_in) || pair.expires_in <= 0) throw new Error('Invalid token response');
  return pair as TokenPair;
}

export function setTokenCookies(response: NextResponse, access: string, refresh: string, expiresIn = ACCESS_SECONDS) {
  const secure = process.env.NODE_ENV === "production";
  response.headers.set('Cache-Control', 'no-store');
  response.cookies.set(ACCESS_COOKIE, access, { httpOnly: true, secure, sameSite: "lax", path: "/", maxAge: expiresIn });
  response.cookies.set(REFRESH_COOKIE, refresh, { httpOnly: true, secure, sameSite: "lax", path: "/", maxAge: REFRESH_SECONDS });
}

export function clearTokenCookies(response: NextResponse) {
  response.headers.set('Cache-Control', 'no-store');
  for (const name of [ACCESS_COOKIE, REFRESH_COOKIE]) response.cookies.set(name, "", { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 0 });
}

export function validateSameOrigin(request: NextRequest) {
  const origin = request.headers.get("origin");
  try {
    if (!origin || new URL(origin).origin !== request.nextUrl.origin) throw new Error('Origin mismatch');
  } catch {
    return NextResponse.json({ detail: "Cross-origin request rejected" }, { status: 403 });
  }
  return null;
}

export function serviceUnavailable() {
  return NextResponse.json({ detail: "Authentication service is temporarily unavailable. Please try again." }, { status: 503, headers: { 'Cache-Control': 'no-store' } });
}

// A failed refresh must never be mistaken for an invalid session during an outage.
export async function refreshSession(base: string, refresh: string): Promise<TokenPair | null> {
  const response = await upstreamFetch(`${base}/auth/refresh`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: refresh }) });
  if (response.status === 401 || response.status === 403) return null;
  if (!response.ok) throw new Error('Refresh service unavailable');
  return parseTokenPair(await response.json());
}
