"""Dependency-free behavioral checks for pure query helpers.

Load the real function bodies in isolation because the full query module imports
external databases and Cognee. These checks do not replace the API test suite.
"""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import uuid

SOURCE = Path(__file__).resolve().parents[1] / 'backend/app/services/query.py'
FUNCTIONS = {'_query_hash', '_assign_confidence_label', '_build_evidence_trail'}
tree = ast.parse(SOURCE.read_text())
module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)] +
                    [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in FUNCTIONS], type_ignores=[])
ns = {'hashlib': hashlib, 'json': json, 'uuid': uuid, 'EvidenceEdge': lambda **kw: SimpleNamespace(**kw)}
exec(compile(ast.fix_missing_locations(module), str(SOURCE), 'exec'), ns)


class QueryRegressionTests(unittest.TestCase):
    def test_hypothesis_opt_in_cannot_reuse_suppressed_answer(self):
        key = ns['_query_hash']
        self.assertNotEqual(key('yield?', 'plot-a', None, None, False), key('yield?', 'plot-a', None, None, True))

    def test_plot_and_dates_partition_cache(self):
        key = ns['_query_hash']
        variants = [('a', None, None), ('b', None, None), ('a', '2025-01-01', None), ('a', None, '2025-12-31')]
        self.assertEqual(len({key('yield?', *v) for v in variants}), 4)

    def test_delimiters_do_not_collide(self):
        key = ns['_query_hash']
        self.assertNotEqual(key('a|b', 'c', None, None), key('a', 'b|c', None, None))

    def test_hash_is_deterministic(self):
        key = ns['_query_hash']
        self.assertEqual(key('yield?', 'a', None, None), key('yield?', 'a', None, None))

    def test_foreign_and_untraceable_evidence_removed(self):
        edges = [
            {'node_id': 'n1', 'source_document_id': 'owned'},
            {'node_id': 'n2', 'source_document_id': 'foreign'},
            {'node_id': 'n3'},
        ]
        result = ns['_build_evidence_trail']({'evidence_edges': edges}, {'owned': object()}, 'query')
        self.assertEqual([e.source_document_id for e in result], ['owned'])

    def test_no_evidence_never_becomes_fact(self):
        self.assertEqual(ns['_assign_confidence_label']({}, []), ('unconfirmed_hypothesis', 0.2))

    def test_mixed_evidence_remains_association(self):
        label, score = ns['_assign_confidence_label']({}, [{'confirmed': True}, {'confirmed': False}])
        self.assertEqual(label, 'statistical_association')
        self.assertLess(score, 0.85)

if __name__ == '__main__':
    unittest.main()
