import { NextRequest, NextResponse } from "next/server";
import { ACCESS_COOKIE, REFRESH_COOKIE, backendUrl, clearTokenCookies, setTokenCookies } from "@/lib/server-auth";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type Context = { params: Promise<{ path: string[] }> };
const allowedMethods = new Set(["GET", "POST", "PUT", "PATCH", "DELETE"]);

async function proxy(request: NextRequest, context: Context) {
  if (!allowedMethods.has(request.method)) return NextResponse.json({ detail: "Method not allowed" }, { status: 405 });
  const origin = request.headers.get("origin");
  if (origin && new URL(origin).host !== request.nextUrl.host) return NextResponse.json({ detail: "Cross-origin request rejected" }, { status: 403 });
  const { path } = await context.params;
  if (path[0] !== "api" || path[1] !== "v1") return NextResponse.json({ detail: "Route not found" }, { status: 404 });

  try {
    const base = backendUrl();
    const upstreamUrl = `${base}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
    const jar = request.cookies;
    let access = jar.get(ACCESS_COOKIE)?.value;
    const refresh = jar.get(REFRESH_COOKIE)?.value;
    const requestBody = request.method === "GET" || request.method === "DELETE" ? undefined : await request.arrayBuffer();
    const forward = async (token?: string) => {
      const headers = new Headers({ Accept: "application/json" });
      const contentType = request.headers.get("content-type");
      if (contentType) headers.set("Content-Type", contentType);
      const range = request.headers.get("range");
      if (range) headers.set("Range", range);
      if (token) headers.set("Authorization", `Bearer ${token}`);
      return fetch(upstreamUrl, {
        method: request.method, headers, cache: "no-store",
        body: requestBody,
      });
    };

    let upstream = await forward(access);
    let newTokens: { access_token: string; refresh_token: string; expires_in: number } | null = null;
    if (upstream.status === 401 && refresh) {
      const refreshed = await fetch(`${base}/auth/refresh`, { method: "POST", cache: "no-store", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: refresh }) });
      if (refreshed.ok) {
        const refreshedTokenPair = await refreshed.json() as { access_token: string; refresh_token: string; expires_in: number };
        newTokens = refreshedTokenPair;
        access = refreshedTokenPair.access_token;
        upstream = await forward(access);
      }
    }
    const headers = new Headers();
    const responseType = upstream.headers.get("content-type");
    if (responseType) headers.set("Content-Type", responseType);
    const requestId = upstream.headers.get("x-request-id");
    if (requestId) headers.set("X-Request-ID", requestId);
    headers.set("Cache-Control", "no-store");
    const response = new NextResponse(upstream.status === 204 ? null : await upstream.arrayBuffer(), { status: upstream.status, headers });
    if (newTokens) setTokenCookies(response, newTokens.access_token, newTokens.refresh_token, newTokens.expires_in);
    else if (upstream.status === 401 && refresh) clearTokenCookies(response);
    return response;
  } catch (error) {
    return NextResponse.json({ detail: error instanceof Error ? error.message : "Backend service is unavailable." }, { status: 503 });
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
