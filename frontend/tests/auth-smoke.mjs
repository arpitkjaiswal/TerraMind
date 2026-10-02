// Exercise built Next route handlers against a deterministic backend, without credentials.
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import assert from 'node:assert/strict';

const origin = 'http://localhost:3100';
let refreshStatus = 200;
let calls = 0;
const user = { id: 'user-1', email: 'farmer@example.com', role: 'farmer', farm_id: 'farm-1' };
const backend = createServer(async (req, res) => {
  calls++;
  const chunks = []; for await (const chunk of req) chunks.push(chunk);
  const body = Buffer.concat(chunks).toString();
  res.setHeader('Content-Type', 'application/json');
  if (req.url.startsWith('/auth/register?')) {
    const registration = JSON.parse(body); assert.equal(registration.role, 'farmer');
    res.statusCode = 201; res.end(JSON.stringify(user));
  } else if (req.url === '/auth/login') {
    assert.equal(new URLSearchParams(body).get('username'), user.email);
    res.end(JSON.stringify({ access_token: 'valid', refresh_token: 'refresh', expires_in: 3600 }));
  } else if (req.url === '/auth/refresh') {
    res.statusCode = refreshStatus;
    res.end(JSON.stringify(refreshStatus === 200 ? { access_token: 'valid', refresh_token: 'renewed', expires_in: 3600 } : { detail: 'Unavailable' }));
  } else if (req.url === '/auth/me') {
    res.statusCode = req.headers.authorization === 'Bearer valid' ? 200 : 401;
    res.end(JSON.stringify(res.statusCode === 200 ? user : { detail: 'Expired' }));
  } else if (req.url === '/auth/logout') { res.end('{}');
  } else if (req.url === '/api/v1/plots/') {
    res.statusCode = req.headers.authorization === 'Bearer valid' ? 200 : 401;
    res.end(JSON.stringify(res.statusCode === 200 ? [{ id: 'real-plot' }] : {}));
  } else { res.statusCode = 404; res.end('{}'); }
});
await new Promise(resolve => backend.listen(3101, '127.0.0.1', resolve));
const app = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'start', '-p', '3100'], { env: { ...process.env, BACKEND_URL: 'http://127.0.0.1:3101' }, stdio: ['ignore', 'pipe', 'pipe'] });
let output = ''; app.stdout.on('data', d => { output += d; }); app.stderr.on('data', d => { output += d; });
const request = (path, init = {}) => fetch(origin + path, { ...init, redirect: 'manual' });
const cookies = 'aegis_access=valid; aegis_refresh=refresh';
try {
  let ready = false;
  for (let i = 0; i < 100; i++) {
    try { if ((await request('/api/auth/session')).ok) { ready = true; break; } } catch {}
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  assert.ok(ready, output);
  let res = await request('/api/auth/login', { method: 'POST', headers: { Origin: origin, 'Content-Type': 'application/json' }, body: JSON.stringify({ email: user.email, password: 'test-password' }) });
  assert.equal(res.status, 200); assert.equal((await res.json()).id, user.id);
  const setCookies = res.headers.getSetCookie();
  assert.equal(setCookies.length, 2); assert.ok(setCookies.every(c => /HttpOnly/i.test(c) && /Secure/i.test(c) && /SameSite=lax/i.test(c)));
  res = await request('/api/auth/register', { method: 'POST', headers: { Origin: origin, 'Content-Type': 'application/json' }, body: JSON.stringify({ email: user.email, password: 'test-password', farm_name: 'Test Farm' }) });
  assert.equal(res.status, 201); assert.equal((await res.json()).id, user.id); assert.equal(res.headers.getSetCookie().length, 2);
  for (const badOrigin of ['null', 'https://localhost:3100', 'http://evil.example']) {
    res = await request('/api/auth/login', { method: 'POST', headers: { Origin: badOrigin }, body: '{}' }); assert.equal(res.status, 403);
  }
  res = await request('/api/auth/login', { method: 'POST', headers: { Origin: origin }, body: 'invalid-json' }); assert.equal(res.status, 400);
  const before = calls;
  res = await request('/api/backend/api/v1/plots'); assert.equal(res.status, 401); assert.equal(calls, before);
  res = await request('/api/backend/api/v1/plots', { headers: { Cookie: cookies } }); assert.equal(res.status, 200); assert.equal((await res.json())[0].id, 'real-plot');
  res = await request('/api/backend/api/v1/plots', { headers: { Cookie: 'aegis_refresh=refresh' } }); assert.equal(res.status, 200); assert.ok(res.headers.get('set-cookie').includes('renewed'));
  refreshStatus = 503;
  for (const path of ['/api/auth/session', '/api/backend/api/v1/plots']) {
    res = await request(path, { headers: { Cookie: 'aegis_access=expired; aegis_refresh=refresh' } });
    assert.equal(res.status, 503); assert.equal(res.headers.get('set-cookie'), null);
  }
  refreshStatus = 401;
  res = await request('/api/backend/api/v1/plots', { headers: { Cookie: 'aegis_refresh=refresh' } }); assert.equal(res.status, 401); assert.ok(res.headers.get('set-cookie').includes('Max-Age=0'));
  res = await request('/api/auth/session', { method: 'DELETE', headers: { Origin: origin, Cookie: cookies } }); assert.equal(res.status, 200); assert.ok(res.headers.getSetCookie().every(c => c.includes('Max-Age=0')));
  console.log('Authentication smoke checks passed: login, secure cookies, origins, malformed input, anonymous rejection, API forwarding, refresh, outage preservation, expiry, logout.');
} finally {
  app.kill('SIGTERM');
  backend.closeAllConnections();
  await new Promise(resolve => backend.close(resolve));
}
