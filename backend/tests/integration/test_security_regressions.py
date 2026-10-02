"""Regression coverage for signup privileges and tenant-scoped operations."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from app.core.auth import create_access_token, create_refresh_token
from app.models.db import Farm, Plot, User


@pytest.mark.asyncio
async def test_signup_cannot_request_admin(client):
    response = await client.post('/auth/register', params={'farm_name': 'Farm'}, json={
        'email': 'new@example.com', 'password': 'long-password', 'role': 'admin',
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_assigns_valid_owner_uuid(client):
    response = await client.post('/auth/register', params={'farm_name': 'Farm'}, json={
        'email': 'new@example.com', 'password': 'long-password',
    })
    assert response.status_code == 201
    uuid.UUID(response.json()['id'])
    assert response.json()['role'] == 'farmer'


@pytest.mark.asyncio
async def test_inactive_user_cannot_refresh(client, test_user, test_farm, db):
    token = create_refresh_token(test_user.id, test_farm.id, 'farmer')
    test_user.is_active = False
    await db.flush()
    response = await client.post('/auth/refresh', json={'refresh_token': token})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_query_rejects_foreign_plot(client, farmer_token, db):
    foreign_farm = Farm(id=str(uuid.uuid4()), name='Other farm', owner_user_id=str(uuid.uuid4()))
    db.add(foreign_farm)
    await db.flush()
    plot = Plot(id=str(uuid.uuid4()), farm_id=foreign_farm.id, name='Other field', crop_type='Rice', size_ha=1)
    db.add(plot)
    await db.flush()
    with patch('app.api.routes.queries.execute_query', new_callable=AsyncMock) as execute:
        response = await client.post('/api/v1/query/', headers={'Authorization': f'Bearer {farmer_token}'},
                                     json={'query_text': 'Why did yield drop?', 'plot_id': plot.id})
    assert response.status_code == 404
    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_document_cannot_read_cached_status(client, farmer_token):
    with patch('app.api.routes.documents.get_ingest_status', new_callable=AsyncMock) as cache:
        cache.return_value = {'status': 'ready', 'detail': 'private'}
        response = await client.get(f'/api/v1/documents/{uuid.uuid4()}/status',
                                    headers={'Authorization': f'Bearer {farmer_token}'})
    assert response.status_code == 404
    cache.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_rejects_unknown_plot_before_ingestion(client, farmer_token):
    with patch('app.api.routes.documents.ingest_document', new_callable=AsyncMock) as ingest:
        response = await client.post('/api/v1/documents/upload',
            headers={'Authorization': f'Bearer {farmer_token}'},
            data={'plot_id': str(uuid.uuid4()), 'label': 'Test'},
            files={'file': ('data.csv', b'a,b\n1,2', 'text/csv')})
    assert response.status_code == 404
    ingest.assert_not_awaited()


@pytest.mark.asyncio
async def test_farm_admin_can_manage_users_within_their_farm(client, test_user, test_farm, db):
    # Authorization uses the current database role, not a stale role claim in
    # a previously issued token.
    token = create_access_token(test_user.id, test_farm.id, 'farmer')
    test_user.role = 'admin'
    await db.flush()
    headers = {'Authorization': f'Bearer {token}'}

    users = await client.get('/api/v1/farms/me/users', headers=headers)
    assert users.status_code == 200
    assert [user['email'] for user in users.json()] == [test_user.email]

    invite = {'email': 'new-farmer@example.com', 'password': 'long-password'}
    created = await client.post('/api/v1/farms/me/users', headers=headers, json=invite)
    assert created.status_code == 201
    assert created.json()['role'] == 'farmer'
    assert created.json()['farm_id'] == test_farm.id

    duplicate = await client.post('/api/v1/farms/me/users', headers=headers, json=invite)
    assert duplicate.status_code == 409


@pytest.mark.asyncio
async def test_farmer_cannot_manage_farm_users(client, farmer_token):
    headers = {'Authorization': f'Bearer {farmer_token}'}
    body = {'name': 'Renamed farm'}
    invite = {'email': 'new-farmer@example.com', 'password': 'long-password'}

    update = await client.put('/api/v1/farms/me', headers=headers, json=body)
    create_user = await client.post('/api/v1/farms/me/users', headers=headers, json=invite)

    assert update.status_code == 403
    assert create_user.status_code == 403
