import { cookies } from "next/headers";
import type { NextRequest, NextResponse } from "next/server";

export const ACCESS_COOKIE = "aegis_access";
export const REFRESH_COOKIE = "aegis_refresh";
export const ACCESS_SECONDS = 60 * 60;
export const REFRESH_SECONDS = 60 * 60 * 24 * 7;

export function backendUrl() {
  const value = process.env.BACKEND_URL?.trim().replace(/\/$/, "");
  if (!value) throw new Error("BACKEND_URL is not configured on the server.");
  return value;
}

export async function getTokens() {
  const jar = await cookies();
  return { access: jar.get(ACCESS_COOKIE)?.value, refresh: jar.get(REFRESH_COOKIE)?.value };
}

export function setTokenCookies(response: NextResponse, access: string, refresh: string, expiresIn = ACCESS_SECONDS) {
  const secure = process.env.NODE_ENV === "production";
  response.cookies.set(ACCESS_COOKIE, access, { httpOnly: true, secure, sameSite: "lax", path: "/", maxAge: expiresIn });
  response.cookies.set(REFRESH_COOKIE, refresh, { httpOnly: true, secure, sameSite: "lax", path: "/", maxAge: REFRESH_SECONDS });
}

export function clearTokenCookies(response: NextResponse) {
  response.cookies.set(ACCESS_COOKIE, "", { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 0 });
  response.cookies.set(REFRESH_COOKIE, "", { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 0 });
}

export function validateSameOrigin(request: NextRequest) {
  const origin = request.headers.get("origin");
  if (origin && new URL(origin).host !== request.nextUrl.host) {
    return Response.json({ detail: "Cross-origin request rejected" }, { status: 403 });
  }
  return null;
}
