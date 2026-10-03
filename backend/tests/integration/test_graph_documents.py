import uuid
from unittest.mock import AsyncMock, patch

import pytest
from neo4j.exceptions import ServiceUnavailable
from app.models.db import Document
from app.models.schemas import GraphEdge, GraphNode


def test_legacy_graph_metadata_can_omit_optional_fields():
    node = GraphNode(id='one', type='Practice', label='Sowing', properties={})
    edge = GraphEdge(source='one', target='two', type='PRECEDED')
    assert node.date is None
    assert edge.date is None and edge.source_document_id is None and edge.confirmed is False


@pytest.mark.asyncio
@pytest.mark.parametrize('graph_unavailable', [False, True])
async def test_saved_documents_appear_in_graph_even_before_extraction(client, db, farmer_token, test_plot, graph_unavailable):
    doc = Document(id=str(uuid.uuid4()), farm_id=test_plot.farm_id, plot_id=test_plot.id, source_type='csv',
                   label='Synthetic sample', storage_uri='s3://test/doc.csv', content_hash='a' * 64,
                   ingest_status='processing', date_of_event='2026-06-01')
    db.add(doc)
    await db.flush()
    with patch('app.api.routes.plots.temporal_subgraph', new_callable=AsyncMock) as graph:
        if graph_unavailable:
            graph.side_effect = ServiceUnavailable('Graph service is down')
        else:
            graph.return_value = {'nodes': [], 'edges': []}
        response = await client.get(f'/api/v1/plots/{test_plot.id}/graph', headers={'Authorization': f'Bearer {farmer_token}'})
    assert response.status_code == 200
    data = response.json()
    assert [n['type'] for n in data['nodes']] == ['Field', 'Document']
    assert data['nodes'][1]['properties']['status'] == 'processing'
    assert data['edges'][0]['source_document_id'] == doc.id
    assert bool(data['warnings']) is graph_unavailable


@pytest.mark.asyncio
async def test_foreign_plot_graph_does_not_query_external_graph(client, farmer_token):
    with patch('app.api.routes.plots.temporal_subgraph', new_callable=AsyncMock) as graph:
        response = await client.get('/api/v1/plots/not-owned/graph', headers={'Authorization': f'Bearer {farmer_token}'})
    assert response.status_code == 404
    graph.assert_not_awaited()
