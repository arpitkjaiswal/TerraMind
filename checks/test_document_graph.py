"""Behavioral checks for the graph's saved-record projection (no external services)."""
import importlib.util
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location('document_graph', Path(__file__).resolve().parents[1] / 'backend/app/services/document_graph.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
merge = module.merge_document_graph

class DocumentGraphTests(unittest.TestCase):
    def setUp(self):
        self.plot = SimpleNamespace(id='plot', farm_id='farm', name='Field', crop_type='Wheat', size_ha=2)
        self.document = dict(id='doc', farm_id='farm', plot_id='plot', date_of_event=date(2026, 6, 1),
                             uploaded_at=datetime(2026, 6, 2, tzinfo=timezone.utc), label='Report', source_type='csv', ingest_status='processing')
        self.empty = {'nodes': [], 'edges': []}

    def test_processing_document_is_visible_without_being_an_agronomic_claim(self):
        graph = merge(self.plot, [SimpleNamespace(**self.document)], self.empty)
        self.assertEqual([node['type'] for node in graph['nodes']], ['Field', 'Document'])
        self.assertEqual(graph['nodes'][1]['properties']['status'], 'processing')
        self.assertEqual(graph['edges'][0]['type'], 'HAS_DOCUMENT')

    def test_foreign_farm_and_plot_documents_are_excluded(self):
        docs = [SimpleNamespace(**{**self.document, 'farm_id': 'foreign'}), SimpleNamespace(**{**self.document, 'plot_id': 'foreign'})]
        graph = merge(self.plot, docs, self.empty)
        self.assertEqual(len(graph['nodes']), 1)
        self.assertFalse(graph['edges'])

    def test_document_dates_are_inclusive_and_fall_back_to_upload_date(self):
        doc = SimpleNamespace(**self.document)
        self.assertEqual(len(merge(self.plot, [doc], self.empty, date(2026, 6, 1), date(2026, 6, 1))['nodes']), 2)
        self.assertEqual(len(merge(self.plot, [doc], self.empty, date(2026, 6, 2))['nodes']), 1)
        doc.date_of_event = None
        self.assertEqual(len(merge(self.plot, [doc], self.empty, date(2026, 6, 2), date(2026, 6, 2))['nodes']), 2)

    def test_existing_field_reused_and_null_or_dangling_edges_removed(self):
        graph = {'nodes': [{'id': 'real-field', 'type': 'Field', 'label': 'Field', 'properties': {}}],
                 'edges': [None, {'source': 'missing', 'target': 'real-field'}]}
        result = merge(self.plot, [SimpleNamespace(**self.document)], graph)
        self.assertEqual(len(result['nodes']), 2)
        self.assertEqual(result['edges'][0]['source'], 'real-field')
        self.assertEqual(len(result['edges']), 1)

if __name__ == '__main__':
    unittest.main()
