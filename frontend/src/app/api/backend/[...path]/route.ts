import { NextRequest, NextResponse } from "next/server";
import { ACCESS_COOKIE, REFRESH_COOKIE, backendUrl, clearTokenCookies, refreshSession, serviceUnavailable, setTokenCookies, upstreamFetch, validateSameOrigin, type TokenPair } from "@/lib/server-auth";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
type Context = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: Context) {
  if (request.method !== 'GET') {
    const rejected = validateSameOrigin(request);
    if (rejected) return rejected;
  }
  const { path } = await context.params;
  if (path[0] !== 'api' || path[1] !== 'v1' || path.length < 3 || path.some(segment => !segment || segment === '.' || segment === '..' || /[\\/]/.test(segment))) return NextResponse.json({ detail: 'Route not found' }, { status: 404 });
  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
  const unauthorized = () => {
    const response = NextResponse.json({ detail: 'Your session expired. Please sign in again.' }, { status: 401 });
    clearTokenCookies(response);
    return response;
  };
  if (!access && !refresh) return unauthorized();
  try {
    const base = backendUrl();
    // FastAPI collection endpoints end in '/'; avoid redirects dropping POST bodies.
    const trailing = path.length === 3 || request.nextUrl.pathname.endsWith('/') ? '/' : '';
    const url = `${base}/${path.map(encodeURIComponent).join('/')}${trailing}${request.nextUrl.search}`;
    const body = request.method === 'GET' ? undefined : await request.arrayBuffer();
    const forward = (token: string) => {
      const headers = new Headers({ Accept: 'application/json', Authorization: `Bearer ${token}` });
      const contentType = request.headers.get('content-type');
      if (contentType) headers.set('Content-Type', contentType);
      return upstreamFetch(url, { method: request.method, headers, body });
    };
    let tokens: TokenPair | null = null;
    let upstream = access ? await forward(access) : null;
    if ((!upstream || upstream.status === 401) && refresh) {
      tokens = await refreshSession(base, refresh);
      if (!tokens) return unauthorized();
      upstream = await forward(tokens.access_token);
    }
    if (!upstream || upstream.status === 401) return unauthorized();
    if (upstream.status >= 300 && upstream.status < 400) return NextResponse.json({ detail: 'Unexpected backend redirect' }, { status: 502 });
    const headers = new Headers({ 'Cache-Control': 'no-store' });
    const type = upstream.headers.get('content-type');
    if (type) headers.set('Content-Type', type);
    const response = new NextResponse(upstream.status === 204 ? null : await upstream.arrayBuffer(), { status: upstream.status, headers });
    if (tokens) setTokenCookies(response, tokens.access_token, tokens.refresh_token, tokens.expires_in);
    return response;
  } catch { return serviceUnavailable(); }
}
export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
