import { NextRequest, NextResponse } from "next/server";
import { backendUrl, setTokenCookies, validateSameOrigin } from "@/lib/server-auth";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const rejected = validateSameOrigin(request);
  if (rejected) return rejected;
  try {
    const body = await request.json() as { email?: unknown; password?: unknown; farm_name?: unknown };
    if (typeof body.email !== "string" || typeof body.password !== "string" || typeof body.farm_name !== "string") {
      return NextResponse.json({ detail: "Email, password, and farm name are required." }, { status: 400 });
    }
    const base = backendUrl();
    const registration = await fetch(`${base}/auth/register?farm_name=${encodeURIComponent(body.farm_name)}`, {
      method: "POST", cache: "no-store", headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ email: body.email, password: body.password, role: "farmer" }),
    });
    if (!registration.ok) return NextResponse.json(await registration.json().catch(() => ({ detail: "Account creation failed." })), { status: registration.status });
    const form = new URLSearchParams({ username: body.email, password: body.password });
    const login = await fetch(`${base}/auth/login`, { method: "POST", cache: "no-store", headers: { "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" }, body: form });
    if (!login.ok) return NextResponse.json({ detail: "Account created, but automatic sign-in failed. Please sign in." }, { status: 502 });
    const tokens = await login.json() as { access_token: string; refresh_token: string; expires_in: number };
    const profile = await fetch(`${base}/auth/me`, { cache: "no-store", headers: { Authorization: `Bearer ${tokens.access_token}` } });
    if (!profile.ok) return NextResponse.json({ detail: "Account created, but its profile could not be loaded. Please sign in." }, { status: 502 });
    const response = NextResponse.json(await profile.json(), { status: 201 });
    setTokenCookies(response, tokens.access_token, tokens.refresh_token, tokens.expires_in);
    return response;
  } catch (error) {
    return NextResponse.json({ detail: error instanceof Error ? error.message : "Authentication service is unavailable." }, { status: 503 });
  }
}
