import { NextRequest, NextResponse } from "next/server";
import { ACCESS_COOKIE, REFRESH_COOKIE, backendUrl, clearTokenCookies, setTokenCookies, validateSameOrigin } from "@/lib/server-auth";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const base = backendUrl();
    const { cookies } = await import("next/headers");
    const jar = await cookies();
    const access = jar.get(ACCESS_COOKIE)?.value;
    const refresh = jar.get(REFRESH_COOKIE)?.value;
    if (!access && !refresh) return NextResponse.json({ user: null }, { status: 200 });

    let token = access;
    let refreshed: { access_token: string; refresh_token: string; expires_in: number } | null = null;
    let profile = token ? await fetch(`${base}/auth/me`, { cache: "no-store", headers: { Authorization: `Bearer ${token}` } }) : null;
    if ((!profile || profile.status === 401) && refresh) {
      const refreshResponse = await fetch(`${base}/auth/refresh`, { method: "POST", cache: "no-store", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: refresh }) });
      if (refreshResponse.ok) {
        const refreshedTokens = await refreshResponse.json() as { access_token: string; refresh_token: string; expires_in: number };
        refreshed = refreshedTokens;
        token = refreshedTokens.access_token;
        profile = await fetch(`${base}/auth/me`, { cache: "no-store", headers: { Authorization: `Bearer ${token}` } });
      }
    }
    if (profile && profile.status >= 500) return NextResponse.json({ user: null, detail: "Authentication service is temporarily unavailable." }, { status: 503 });
    if (!profile?.ok) {
      const response = NextResponse.json({ user: null }, { status: 200 });
      clearTokenCookies(response);
      return response;
    }
    const response = NextResponse.json({ user: await profile.json() });
    if (refreshed) setTokenCookies(response, refreshed.access_token, refreshed.refresh_token, refreshed.expires_in);
    return response;
  } catch (error) {
    return NextResponse.json({ user: null, detail: error instanceof Error ? error.message : "Authentication service is unavailable." }, { status: 503 });
  }
}

export async function DELETE(request: NextRequest) {
  const rejected = validateSameOrigin(request);
  if (rejected) return rejected;
  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  try {
    if (access) await fetch(`${backendUrl()}/auth/logout`, { method: "POST", cache: "no-store", headers: { Authorization: `Bearer ${access}` } });
  } catch { /* Local session is cleared even when the backend is unavailable. */ }
  const response = NextResponse.json({ detail: "Signed out." });
  clearTokenCookies(response);
  return response;
}
