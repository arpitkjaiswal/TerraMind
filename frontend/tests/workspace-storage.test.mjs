import test from 'node:test';
import assert from 'node:assert/strict';
import { restoreWorkspace } from '../src/lib/workspace-storage.ts';

const document = { id: 'sample', plot_id: 'B', label: 'Weather', source_type: 'csv', storage_uri: 'local://sample', ingest_status: 'ready', uploaded_at: '2026-01-01', source_confidence: 0.8 };
const defaults = { documents: [document], timeline: [], queue: [], totalQueries: 0 };
test('malformed browser storage cannot enter rendering state', () => {
  for (const value of ['{', 'null', '[]', JSON.stringify({ ...defaults, documents: [null] }), JSON.stringify({ ...defaults, totalQueries: -1 }), JSON.stringify({ ...defaults, documents: [{ ...document, uploaded_at: 'bad' }] }), JSON.stringify({ ...defaults, timeline: [null] }), JSON.stringify({ ...defaults, queue: [null] })]) {
    assert.equal(restoreWorkspace(value, defaults, []), defaults);
  }
});
test('valid changes survive restoration and sample records are not duplicated', () => {
  const saved = { ...defaults, documents: [{ ...document, extracted_text: 'rainfall: 15' }], totalQueries: 4 };
  const restored = restoreWorkspace(JSON.stringify(saved), defaults, [document, { ...document, id: 'second' }]);
  assert.equal(restored.totalQueries, 4);
  assert.equal(restored.documents.length, 2);
  assert.equal(restored.documents[0].extracted_text, 'rainfall: 15');
});
