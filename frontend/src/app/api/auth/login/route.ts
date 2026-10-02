import { NextRequest, NextResponse } from "next/server";
import { backendUrl, setTokenCookies, validateSameOrigin } from "@/lib/server-auth";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const rejected = validateSameOrigin(request);
  if (rejected) return rejected;
  try {
    const { email, password } = await request.json();
    if (typeof email !== "string" || typeof password !== "string") return NextResponse.json({ detail: "Enter your email and password." }, { status: 400 });
    const upstream = await fetch(`${backendUrl()}/auth/login`, {
      method: "POST", cache: "no-store",
      headers: { "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" },
      body: new URLSearchParams({ username: email, password }),
    });
    if (!upstream.ok) return NextResponse.json(await upstream.json().catch(() => ({ detail: "Sign-in failed." })), { status: upstream.status });
    const tokens = await upstream.json() as { access_token: string; refresh_token: string; expires_in: number };
    const profile = await fetch(`${backendUrl()}/auth/me`, { cache: "no-store", headers: { Authorization: `Bearer ${tokens.access_token}` } });
    if (!profile.ok) return NextResponse.json({ detail: "Signed in, but the account profile could not be loaded." }, { status: 502 });
    const response = NextResponse.json(await profile.json());
    setTokenCookies(response, tokens.access_token, tokens.refresh_token, tokens.expires_in);
    return response;
  } catch (error) {
    return NextResponse.json({ detail: error instanceof Error ? error.message : "Authentication service is unavailable." }, { status: 503 });
  }
}
