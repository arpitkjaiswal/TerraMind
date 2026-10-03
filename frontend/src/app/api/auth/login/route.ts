import { NextRequest, NextResponse } from "next/server";
import { backendUrl, parseTokenPair, serviceUnavailable, setTokenCookies, upstreamFetch, validateSameOrigin } from "@/lib/server-auth";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const rejected = validateSameOrigin(request);
  if (rejected) return rejected;
  try {
    const body = await request.json().catch(() => null);
    if (!body || typeof body !== "object") return NextResponse.json({ detail: "Invalid request body." }, { status: 400 });
    const { email, password } = body;
    if (typeof email !== "string" || typeof password !== "string") return NextResponse.json({ detail: "Enter your email and password." }, { status: 400 });
    const upstream = await upstreamFetch(`${backendUrl()}/auth/login`, {
      method: "POST", cache: "no-store",
      headers: { "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" },
      body: new URLSearchParams({ username: email, password }),
    });
    if (!upstream.ok) return NextResponse.json(await upstream.json().catch(() => ({ detail: "Sign-in failed." })), { status: upstream.status });
    const tokens = parseTokenPair(await upstream.json());
    const profile = await upstreamFetch(`${backendUrl()}/auth/me`, { cache: "no-store", headers: { Authorization: `Bearer ${tokens.access_token}` } });
    if (!profile.ok) return NextResponse.json({ detail: "Signed in, but the account profile could not be loaded." }, { status: 502 });
    const response = NextResponse.json(await profile.json());
    setTokenCookies(response, tokens.access_token, tokens.refresh_token, tokens.expires_in);
    return response;
  } catch { return serviceUnavailable(); }
}
