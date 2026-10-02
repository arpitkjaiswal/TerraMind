import { NextRequest, NextResponse } from "next/server";
import { backendUrl, parseTokenPair, serviceUnavailable, setTokenCookies, upstreamFetch, validateSameOrigin } from "@/lib/server-auth";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const rejected = validateSameOrigin(request);
  if (rejected) return rejected;
  try {
    const body = await request.json().catch(() => null) as { email?: unknown; password?: unknown; farm_name?: unknown } | null;
    if (!body) return NextResponse.json({ detail: "Invalid request body." }, { status: 400 });
    if (typeof body.email !== "string" || typeof body.password !== "string" || typeof body.farm_name !== "string") {
      return NextResponse.json({ detail: "Email, password, and farm name are required." }, { status: 400 });
    }
    const base = backendUrl();
    const registration = await upstreamFetch(`${base}/auth/register?farm_name=${encodeURIComponent(body.farm_name)}`, {
      method: "POST", cache: "no-store", headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ email: body.email, password: body.password, role: "farmer" }),
    });
    if (!registration.ok) return NextResponse.json(await registration.json().catch(() => ({ detail: "Account creation failed." })), { status: registration.status });
    const form = new URLSearchParams({ username: body.email, password: body.password });
    const login = await upstreamFetch(`${base}/auth/login`, { method: "POST", cache: "no-store", headers: { "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" }, body: form });
    if (!login.ok) return NextResponse.json({ detail: "Account created, but automatic sign-in failed. Please sign in." }, { status: 502 });
    const tokens = parseTokenPair(await login.json());
    const profile = await upstreamFetch(`${base}/auth/me`, { cache: "no-store", headers: { Authorization: `Bearer ${tokens.access_token}` } });
    if (!profile.ok) return NextResponse.json({ detail: "Account created, but its profile could not be loaded. Please sign in." }, { status: 502 });
    const response = NextResponse.json(await profile.json(), { status: 201 });
    setTokenCookies(response, tokens.access_token, tokens.refresh_token, tokens.expires_in);
    return response;
  } catch { return serviceUnavailable(); }
}
