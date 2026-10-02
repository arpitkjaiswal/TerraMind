import { NextRequest, NextResponse } from "next/server";
import { ACCESS_COOKIE, backendUrl, clearTokenCookies, getTokens, refreshSession, serviceUnavailable, setTokenCookies, upstreamFetch, validateSameOrigin, type TokenPair } from "@/lib/server-auth";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const { access, refresh } = await getTokens();
    if (!access && !refresh) return NextResponse.json({ user: null }, { headers: { 'Cache-Control': 'no-store' } });
    const base = backendUrl();
    let tokens: TokenPair | null = null;
    let profile = access ? await upstreamFetch(`${base}/auth/me`, { headers: { Authorization: `Bearer ${access}` } }) : null;
    if ((!profile || profile.status === 401) && refresh) {
      tokens = await refreshSession(base, refresh);
      profile = tokens ? await upstreamFetch(`${base}/auth/me`, { headers: { Authorization: `Bearer ${tokens.access_token}` } }) : null;
    }
    if (profile && !profile.ok && ![401, 403].includes(profile.status)) return serviceUnavailable();
    if (!profile?.ok) {
      const response = NextResponse.json({ user: null }, { headers: { 'Cache-Control': 'no-store' } });
      clearTokenCookies(response);
      return response;
    }
    const response = NextResponse.json({ user: await profile.json() }, { headers: { 'Cache-Control': 'no-store' } });
    if (tokens) setTokenCookies(response, tokens.access_token, tokens.refresh_token, tokens.expires_in);
    return response;
  } catch { return serviceUnavailable(); }
}

export async function DELETE(request: NextRequest) {
  const rejected = validateSameOrigin(request);
  if (rejected) return rejected;
  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  try {
    if (access) await upstreamFetch(`${backendUrl()}/auth/logout`, { method: "POST", headers: { Authorization: `Bearer ${access}` } });
  } catch { /* Browser logout succeeds even during an API outage. */ }
  const response = NextResponse.json({ detail: "Signed out." });
  clearTokenCookies(response);
  return response;
}
