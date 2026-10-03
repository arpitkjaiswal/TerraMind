"""API boundary regressions: reject bad input before external work or writes."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.core.auth import TokenData
from app.models.schemas import PlotCreate, PlotUpdate, QueryRequest, UserCreate


@pytest.mark.parametrize('farm_name', ['', '   ', 'x' * 256])
@pytest.mark.asyncio
async def test_registration_validates_farm_name(client, farm_name):
    response = await client.post('/auth/register', params={'farm_name': farm_name},
        json={'email': 'new@example.com', 'password': 'long-password'})
    assert response.status_code == 422


@pytest.mark.parametrize('value', ['2026-02-30', '2026-13-01'])
def test_query_rejects_impossible_dates(value):
    with pytest.raises(ValidationError):
        QueryRequest(query_text='What happened?', plot_id='plot', date_from=value)


@pytest.mark.parametrize('schema', [PlotCreate, PlotUpdate])
def test_plot_size_must_be_finite(schema):
    with pytest.raises(ValidationError):
        schema(name='Field', crop_type='Rice', size_ha=float('inf'))


def test_updated_crop_fits_database_column():
    with pytest.raises(ValidationError):
        PlotUpdate(crop_type='x' * 256)


@pytest.mark.asyncio
@pytest.mark.parametrize('params', [
    {'date_from': '2026-02-30'},
    {'date_from': '2026-10-02', 'date_to': '2026-01-01'},
])
async def test_graph_rejects_invalid_dates(client, farmer_token, test_plot, params):
    with patch('app.api.routes.plots.temporal_subgraph', new_callable=AsyncMock) as graph:
        response = await client.get(f'/api/v1/plots/{test_plot.id}/graph', params=params,
            headers={'Authorization': f'Bearer {farmer_token}'})
    assert response.status_code == 422
    graph.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_validates_event_date(client, farmer_token, test_plot):
    with patch('app.api.routes.documents.ingest_document', new_callable=AsyncMock) as ingest:
        response = await client.post('/api/v1/documents/upload',
            headers={'Authorization': f'Bearer {farmer_token}'},
            data={'plot_id': test_plot.id, 'label': 'Report', 'date_of_event': '2026-02-30'},
            files={'file': ('report.csv', b'a,b\n1,2', 'text/csv')})
    assert response.status_code == 422
    ingest.assert_not_awaited()


@pytest.mark.asyncio
async def test_reject_endpoint_cannot_approve(client, farmer_token):
    with patch('app.api.routes.documents.reject_document', new_callable=AsyncMock) as reject:
        response = await client.post('/api/v1/documents/unknown/reject',
            headers={'Authorization': f'Bearer {farmer_token}'}, json={'action': 'approve'})
    assert response.status_code == 400
    reject.assert_not_awaited()


@pytest.mark.asyncio
async def test_concurrent_user_creation_returns_conflict():
    from app.api.routes.farms import add_farm_user
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: None)
    db.flush.side_effect = IntegrityError('insert', {}, Exception('duplicate email'))
    with pytest.raises(HTTPException) as error:
        await add_farm_user(UserCreate(email='new@example.com', password='long-password'),
            td=TokenData('user', 'farm', 'admin'), db=db)
    assert error.value.status_code == 409
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_default_rate_limit_is_enforced(client):
    # An undecorated endpoint must be protected by the shared middleware.
    for _ in range(100):
        response = await client.get('/auth/me')
        assert response.status_code == 401
    response = await client.get('/auth/me')
    assert response.status_code == 429
