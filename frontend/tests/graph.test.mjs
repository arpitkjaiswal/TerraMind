import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { emptyFilters, filterGraph, seedParticles, tickParticles, fitCamera, zoomAt } from '../src/lib/graph.ts';
import { buildDemoGraph } from '../src/lib/demo-graph.ts';
import { sampleDocuments, sampleDemoDocuments } from '../src/data/sample-documents.ts';

const nodes = [
  { id: 'field', type: 'Field', label: 'Field', properties: {} },
  { id: 'a', type: 'WeatherEvent', label: 'Rain', date: '2026-01-20', properties: { rainfall_mm: 20 } },
  { id: 'b', type: 'Practice', label: 'Irrigation', date: '2026-06-20', properties: {} },
];
const edges = [
  { id: 'e1', source: 'a', target: 'field', type: 'OCCURRED_DURING', confirmed: true },
  { id: 'e2', source: 'b', target: 'field', type: 'APPLIED_TO', confirmed: false },
  { id: 'orphan', source: 'unknown', target: 'field', confirmed: true },
];
const size = { x: 900, y: 600 };

test('search/type/date filters remove nodes and never leave dangling relationships', () => {
  const data = filterGraph(nodes, edges, { ...emptyFilters, to: '2026-03-01' });
  assert.deepEqual(data.nodes.map(n => n.id), ['field', 'a']);
  assert.deepEqual(data.edges.map(e => e.id), ['e1']);
  assert.equal(filterGraph(nodes, edges, { ...emptyFilters, query: 'missing' }).nodes.length, 0);
  assert.deepEqual(filterGraph(nodes, edges, { ...emptyFilters, type: 'Practice' }).nodes.map(n => n.id), ['b']);
  assert.equal(filterGraph(nodes, edges, { ...emptyFilters, query: '20' }).nodes[0].id, 'a');
});
test('reversed ranges are empty; confirmed-only applies to links', () => {
  assert.equal(filterGraph(nodes, edges, { ...emptyFilters, from: '2026-12-01', to: '2026-01-01' }).nodes.length, 0);
  assert.deepEqual(filterGraph(nodes, edges, { ...emptyFilters, confirmed: true }).edges.map(e => e.id), ['e1']);
});
test('the force simulation moves neighbors but holds the dragged node', () => {
  const particles = seedParticles(nodes, size);
  const original = { ...particles.get('a') }, field = { ...particles.get('field') };
  for (let i = 0; i < 30; i++) tickParticles(particles, edges, size, 1, 'a');
  assert.equal(particles.get('a').x, original.x);
  assert.equal(particles.get('a').y, original.y);
  assert.notEqual(particles.get('field').x, field.x);
  assert.ok([...particles.values()].every(p => Number.isFinite(p.x) && Number.isFinite(p.y)));
});
test('adding/removing records retains existing positions and multiple fields do not overlap', () => {
  const particles = seedParticles(nodes, size);
  particles.get('a').x = 345;
  const updated = seedParticles([...nodes.slice(1), { ...nodes[0], id: 'new-field' }], size, particles);
  assert.equal(updated.get('a').x, 345);
  assert.ok(!updated.has('field'));
  const fields = seedParticles([{ ...nodes[0], id: 'one' }, { ...nodes[0], id: 'two' }], size);
  assert.notDeepEqual(fields.get('one'), fields.get('two'));
});
test('zoom remains anchored and fit-to-view includes all points at desktop/mobile sizes', () => {
  const initial = { pan: { x: 125, y: -25 }, zoom: 1.5 }, anchor = { x: 350, y: 250 };
  const result = zoomAt(initial, 1.5, anchor);
  assert.equal((anchor.x - result.pan.x) / result.zoom, (anchor.x - initial.pan.x) / initial.zoom);
  assert.equal((anchor.y - result.pan.y) / result.zoom, (anchor.y - initial.pan.y) / initial.zoom);
  const points = [{ x: -450, y: 100 }, { x: 1800, y: 900 }];
  for (const viewport of [size, { x: 320, y: 480 }]) {
    const camera = fitCamera(points, viewport);
    for (const point of points) {
      const x = point.x * camera.zoom + camera.pan.x, y = point.y * camera.zoom + camera.pan.y;
      assert.ok(x > 0 && x < viewport.x && y > 0 && y < viewport.y);
    }
  }
});
test('all 18 downloadable CSVs exist, have unique IDs, and label every row synthetic', () => {
  assert.equal(sampleDocuments.length, 18);
  assert.equal(new Set(sampleDocuments.map(s => s.id)).size, 18);
  for (const sample of sampleDocuments) {
    const csv = readFileSync(new URL(`../public/sample-documents/${sample.filename}`, import.meta.url), 'utf8');
    const rows = csv.trim().split(/\r?\n/);
    assert.ok(rows.length > 1);
    assert.ok(rows.slice(1).every(row => row.startsWith('SYNTHETIC_DEMO_NOT_REAL_FARM_DATA,')));
    assert.equal(sample.properties.synthetic, true);
    assert.ok(sample.label.startsWith('Synthetic sample'));
  }
});
test('demo graph is field scoped and updates after an upload or review', () => {
  const plot = { id: 'plot-A', name: 'Field A', crop_type: 'Wheat', size_ha: 42.5 };
  const graph = buildDemoGraph(plot, sampleDemoDocuments, sampleDocuments);
  assert.equal(graph.nodes.length, 13); // Field + 6 documents + 6 sample entities.
  assert.equal(graph.edges.length, 12);
  assert.ok(graph.edges.every(e => e.type !== 'CONFIRMED_CAUSE'));
  const uploaded = { ...sampleDemoDocuments[0], id: 'new-upload', ingest_status: 'processing' };
  const pending = buildDemoGraph(plot, [...sampleDemoDocuments, uploaded], sampleDocuments);
  assert.equal(pending.nodes.length, 14);
  assert.equal(pending.nodes.find(n => n.id === 'document-new-upload').properties.status, 'processing');
  const failed = buildDemoGraph(plot, [{ ...sampleDemoDocuments[0], ingest_status: 'ingest_failed' }], sampleDocuments);
  assert.equal(failed.nodes.length, 2); // Failed sample metadata remains, extracted claims do not.
});
