/** Real browser coverage of the graph and sample-upload flow; all API writes are mocked. */
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { chromium } from 'playwright';

const origin = 'http://127.0.0.1:3200';
const app = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'start', '-p', '3200'], { stdio: ['ignore', 'pipe', 'pipe'] });
let logs = '';
app.stdout.on('data', data => { logs += data; }); app.stderr.on('data', data => { logs += data; });
let browser;
const waitFor = async (condition, message) => {
  for (let i = 0; i < 100; i++) { if (await condition()) return; await new Promise(resolve => setTimeout(resolve, 100)); }
  throw new Error(message);
};
try {
  await waitFor(async () => { try { return (await fetch(origin)).ok; } catch { return false; } }, 'Next did not start: ' + logs);
  const executablePath = process.env.CHROMIUM_PATH || (existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined);
  browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let sessionRequests = 0;
  await page.route('**/api/auth/session', route => { sessionRequests++; return route.fulfill({ status: 503, json: { detail: 'Backend offline' } }); });
  await page.goto(origin);
  await page.getByRole('heading', { name: /Field B/ }).first().waitFor();
  assert.equal(sessionRequests, 0, 'The public sandbox must never depend on authentication');
  assert.equal(await page.getByRole('button', { name: 'Sign in', exact: true }).count(), 0);
  await page.getByRole('button', { name: 'Knowledge Graph', exact: true }).click();
  const graphNodes = page.locator('[data-graph-node]');
  await waitFor(async () => await graphNodes.count() === 23, 'Expected the original graph plus 6 new sample documents and entities');
  await page.getByRole('button', { name: 'Pause layout', exact: true }).click();
  const node = page.locator('[data-graph-node="n-field-B"]');
  await node.click();
  await page.getByRole('complementary', { name: 'Selected entity details' }).waitFor();
  const before = await node.getAttribute('transform');
  const box = await node.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + 25);
  await page.mouse.down(); await page.mouse.move(box.x + box.width / 2 + 65, box.y + 65, { steps: 6 }); await page.mouse.up();
  assert.notEqual(await node.getAttribute('transform'), before, 'Dragging must move a node');
  await page.getByLabel('Search entities').fill('nonexistent-record');
  await waitFor(async () => await graphNodes.count() === 0, 'Search must actually filter');
  await page.getByRole('button', { name: 'Reset graph view' }).click();
  await page.getByLabel('Filter by entity type').selectOption('Document');
  await waitFor(async () => await graphNodes.count() === 11, 'Document type filter must show 11 documents');
  await page.getByLabel('Graph end date').fill('2026-03-01');
  await waitFor(async () => await graphNodes.count() === 3, 'Date range must filter documents');
  await page.getByRole('button', { name: 'Reset graph view' }).click();
  await page.getByRole('button', { name: 'Fit graph', exact: true }).click();
  const download = page.waitForEvent('download');
  await page.getByLabel('Export visible graph').click();
  assert.equal((await download).suggestedFilename(), 'terramind-graph.json');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Fit graph', exact: true }).click();
  assert.ok(await page.locator('svg[aria-label^="Interactive knowledge"]').isVisible());
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole('button', { name: 'Ingest & Review', exact: true }).click();
  assert.equal(await page.locator('a[download][href^="/sample-documents/"]').count(), 6);
  const csv = await page.request.get(origin + '/sample-documents/synthetic-field-b-weather.csv');
  assert.equal(csv.status(), 200); assert.match(await csv.text(), /SYNTHETIC_DEMO_NOT_REAL_FARM_DATA/);
  const beforeUpload = await page.locator('[data-graph-node]').count(); // Graph is unmounted in capture.
  assert.equal(beforeUpload, 0);
  await page.locator('input[type="file"]').first().setInputFiles({ name: 'new-observation.csv', mimeType: 'text/csv', buffer: Buffer.from('date,rainfall_mm\n2026-09-30,15') });
  await page.getByText('new-observation.csv', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Knowledge Graph', exact: true }).click();
  await waitFor(async () => await graphNodes.count() === 24, 'A demo upload must add a document node');
  await page.getByRole('button', { name: 'Ask TerraMind', exact: true }).click();
  await page.getByRole('textbox', { name: 'Ask about field records' }).fill('rainfall');
  await page.getByRole('button', { name: 'Search field records', exact: true }).click();
  await page.getByText(/rainfall_mm: 15/).waitFor();
  await page.reload();
  await page.getByRole('button', { name: 'Knowledge Graph', exact: true }).click();
  await waitFor(async () => await graphNodes.count() === 24, 'Uploaded records must survive reload');
  for (const [action, expected] of [['approve', 'ready'], ['reject', 'ingest_failed']]) {
    await page.getByRole('button', { name: 'Ingest & Review', exact: true }).click();
    const filename = `local-${action}.png`;
    await page.locator('input[type="file"]').first().setInputFiles({ name: filename, mimeType: 'image/png', buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aPiUAAAAASUVORK5CYII=', 'base64') });
    let uploadedId;
    await waitFor(async () => {
      uploadedId = await page.evaluate(name => JSON.parse(localStorage.getItem('aegis-demo-data-v1')).documents.find(doc => doc.label === name)?.id, filename);
      return !!uploadedId;
    }, 'Image record must be saved for review');
    await page.locator(`[id="btn-${action}-upload-${uploadedId}"]`).click();
    await waitFor(async () => await page.evaluate(({ id, status }) => JSON.parse(localStorage.getItem('aegis-demo-data-v1')).documents.find(doc => doc.id === id)?.ingest_status === status, { id: uploadedId, status: expected }), 'Review must update the saved document status');
  }
  await page.getByRole('button', { name: /^Field A/ }).click();
  await page.getByRole('button', { name: 'Knowledge Graph', exact: true }).click();
  assert.equal(await page.locator('[data-graph-node^="document-doc-local-"]').count(), 0);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForFunction(() => getComputedStyle(document.querySelector('aside')).position === 'static');
  const sidebar = await page.locator('aside').first().boundingBox();
  const main = await page.locator('main').boundingBox();
  assert.ok(main.y >= sidebar.y + sidebar.height - 1, `Mobile navigation must not cover the workspace: ${JSON.stringify({ sidebar, main })}`);
  await page.evaluate(() => localStorage.setItem('aegis-demo-data-v1', JSON.stringify({ documents: [null] })));
  await page.reload();
  await page.getByRole('button', { name: 'Knowledge Graph', exact: true }).click();
  await waitFor(async () => await graphNodes.count() === 23, 'Corrupt saved state must recover to defaults');
  await page.close();

  // A signed-in workspace, including a delayed response from the old field.
  const live = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
  live.on('pageerror', error => errors.push(error.message));
  const plots = ['A', 'B'].map(id => ({ id, farm_id: 'farm', name: `Live Field ${id}`, crop_type: 'Corn', size_ha: 10, created_at: '2026-01-01' }));
  const docs = [];
  let uploads = 0, slowA = false, aRequests = 0;
  await live.route('**/api/auth/session', route => route.fulfill({ json: { user: { id: 'test', farm_id: 'farm', email: 'test@example.com', role: 'farmer' } } }));
  await live.route('**/api/backend/**', async route => {
    const path = new URL(route.request().url()).pathname.split('/api/v1/')[1];
    let data;
    if (path === 'farms/me') data = { id: 'farm', name: 'Test Farm', owner_user_id: 'test' };
    else if (path === 'plots/') data = plots;
    else if (path === 'documents/') data = docs;
    else if (path === 'documents/review-queue' || path?.startsWith('query/history')) data = [];
    else if (path === 'documents/upload') {
      assert.equal(route.request().method(), 'POST');
      assert.match(route.request().postData(), /SYNTHETIC_DEMO_NOT_REAL_FARM_DATA/);
      assert.match(route.request().postData(), /name="plot_id"\r\n\r\nB/);
      uploads++;
      docs.push({ id: `doc-${uploads}`, plot_id: 'B', source_type: 'csv', label: `Synthetic sample ${uploads}`, ingest_status: 'processing', uploaded_at: '2026-09-30T09:00:00Z' });
      data = { document_id: `doc-${uploads}`, ingest_status: 'processing' };
    } else if (path?.endsWith('/graph')) {
      const id = path.split('/')[1];
      if (id === 'A') { aRequests++; if (slowA) await new Promise(resolve => setTimeout(resolve, 700)); }
      data = { plot_id: id, nodes: [{ id: `live-${id}`, label: `Live graph ${id}`, type: 'Field', properties: {} }, ...docs.filter(doc => doc.plot_id === id).map(doc => ({ id: doc.id, label: doc.label, type: 'Document', properties: { status: doc.ingest_status } }))], edges: [] };
    } else throw new Error('Unexpected API request ' + path);
    if (!route.request().isNavigationRequest()) await route.fulfill({ json: data }).catch(() => {});
  });
  await live.goto(origin + "/live");
  await live.getByRole('button', { name: 'Knowledge Graph', exact: true }).click();
  await live.locator('[data-graph-node="live-A"]').waitFor();
  slowA = true;
  const requestsBefore = aRequests;
  await live.getByRole('button', { name: 'Refresh graph', exact: true }).click();
  await waitFor(() => aRequests > requestsBefore, 'Refresh request did not start');
  await live.getByRole('button', { name: /^Live Field B/ }).click();
  await live.getByRole('button', { name: 'Knowledge Graph', exact: true }).click();
  await live.locator('[data-graph-node="live-B"]').waitFor();
  await new Promise(resolve => setTimeout(resolve, 850));
  assert.equal(await live.locator('[data-graph-node="live-A"]').count(), 0, 'An old field response must not overwrite the current graph');
  await live.getByRole('button', { name: 'Ingest & Review', exact: true }).click();
  await live.getByRole('button', { name: 'Import 6 synthetic documents', exact: true }).click();
  await waitFor(() => uploads === 6, 'Expected six authenticated sample uploads');
  await live.getByText(/6 of 6 documents accepted/).waitFor();
  docs.forEach(doc => { doc.ingest_status = 'ready'; });
  await live.getByRole('button', { name: 'Knowledge Graph', exact: true }).click();
  await waitFor(async () => await live.locator('[data-graph-node]').count() === 7, 'Uploaded samples must appear on the live graph');
  await live.getByRole('button', { name: 'Ingest & Review', exact: true }).click();
  await waitFor(async () => await live.getByText('ready', { exact: true }).count() === 6, 'Processing statuses must refresh automatically');
  assert.deepEqual(errors, []);
  console.log('Browser checks passed: direct anonymous access, CSV search, persistence, approval/rejection, corrupt-state recovery, mobile navigation, graph drag/select/filter/date/fit/export, sample downloads, field isolation/races, live sample imports, processing refresh.');
} finally {
  await browser?.close(); app.kill('SIGTERM');
}
