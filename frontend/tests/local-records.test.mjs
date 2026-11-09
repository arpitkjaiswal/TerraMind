import test from 'node:test';
import assert from 'node:assert/strict';
import { parseCsv, csvRecordText, searchRecords } from '../src/lib/local-records.ts';

test('CSV handles BOM, CRLF, quoted commas, escaped quotes and multiline cells', () => {
  assert.deepEqual(parseCsv('\uFEFFdate,note\r\n2026-01-01,"Rain, then ""sun"""\r\n2026-01-02,"two\nlines"'), [
    ['date', 'note'], ['2026-01-01', 'Rain, then "sun"'], ['2026-01-02', 'two\nlines'],
  ]);
  assert.equal(csvRecordText('date,rainfall_mm\n2026-01-01,15'), 'date: 2026-01-01 · rainfall_mm: 15');
});

test('invalid or oversized CSV fails with an actionable error', () => {
  for (const csv of ['', 'date,note', 'date,date\n1,2', 'date,note\n1', 'date,note\n1,"oops', 'date,note\n1,"a"tail']) {
    assert.throws(() => parseCsv(csv));
  }
  assert.throws(() => parseCsv('a'.repeat(256001)), /256 KB/);
  assert.throws(() => parseCsv('x\n' + '1\n'.repeat(501)), /500 data rows/);
});

const doc = (id, label, extra = {}) => ({ id, label, plot_id: 'B', uploaded_at: '2026-01-01', ingest_status: 'ready', ...extra });
test('retrieval uses question terms, parsed rows and dates, and excludes unreviewed records', () => {
  const docs = [doc('soil', 'Soil survey'), doc('weather', 'Weather log', { extracted_text: 'rainfall_mm: 15' }), doc('pending', 'Rainfall awaiting review', { ingest_status: 'review_needed' })];
  assert.deepEqual(searchRecords('Show rainfall', docs).map(d => d.id), ['weather']);
  assert.deepEqual(searchRecords('Show rainfall_mm', docs).map(d => d.id), ['weather']);
  assert.deepEqual(searchRecords('soil', docs).map(d => d.id), ['soil']);
  assert.deepEqual(searchRecords('2026', docs).map(d => d.id), ['soil', 'weather']);
  assert.equal(searchRecords('unrelated', docs).length, 0);
  assert.equal(searchRecords('what are the records', docs, 1).length, 1);
});
