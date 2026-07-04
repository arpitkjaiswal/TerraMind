"""
Integration tests — API endpoints via ASGI test client.
"""

import pytest


@pytest.mark.asyncio
class TestAuthRoutes:
    async def test_login_invalid_credentials(self, client):
        resp = await client.post("/auth/login", data={"username": "nobody@test.com", "password": "wrong"})
        assert resp.status_code == 401

    async def test_me_unauthenticated(self, client):
        resp = await client.get("/auth/me")
        assert resp.status_code == 401

    async def test_me_authenticated(self, client, farmer_token):
        resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {farmer_token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "farmer@test.com"


@pytest.mark.asyncio
class TestPlotRoutes:
    async def test_list_plots_empty(self, client, farmer_token):
        resp = await client.get("/api/v1/plots/", headers={"Authorization": f"Bearer {farmer_token}"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_create_plot(self, client, farmer_token):
        resp = await client.post(
            "/api/v1/plots/",
            json={"name": "Field A", "crop_type": "Wheat", "size_ha": 25.0},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Field A"
        assert data["crop_type"] == "Wheat"

    async def test_create_plot_negative_size_rejected(self, client, farmer_token):
        resp = await client.post(
            "/api/v1/plots/",
            json={"name": "Bad", "crop_type": "Corn", "size_ha": -5.0},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 422

    async def test_get_plot_not_owned(self, client, farmer_token):
        resp = await client.get(
            "/api/v1/plots/nonexistent-id",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestQueryRoutes:
    async def test_query_requires_auth(self, client, test_plot):
        resp = await client.post(
            "/api/v1/query/",
            json={"query_text": "Why did yield drop?", "plot_id": test_plot.id},
        )
        assert resp.status_code == 401

    async def test_query_too_short_rejected(self, client, farmer_token, test_plot):
        resp = await client.post(
            "/api/v1/query/",
            json={"query_text": "Why", "plot_id": test_plot.id},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 422

    async def test_query_date_range_validation(self, client, farmer_token, test_plot):
        resp = await client.post(
            "/api/v1/query/",
            json={
                "query_text": "Why did yield drop in 2026?",
                "plot_id": test_plot.id,
                "date_from": "2026-12-01",
                "date_to": "2026-01-01",  # before date_from
            },
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 422

    async def test_query_returns_response_shape(self, client, farmer_token, test_plot):
        resp = await client.post(
            "/api/v1/query/",
            json={"query_text": "Why did Field B yield drop in 2026?", "plot_id": test_plot.id},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Verify first-class fields are present
        assert "answer_text" in data
        assert "confidence_label" in data
        assert "confidence_score" in data
        assert "evidence_trail" in data
        assert "graph_hops" in data
        assert "latency_ms" in data
        assert "cache_hit" in data
        assert data["confidence_label"] in (
            "documented_fact", "statistical_association", "unconfirmed_hypothesis"
        )

    async def test_query_history_empty(self, client, farmer_token):
        resp = await client.get(
            "/api/v1/query/history",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


@pytest.mark.asyncio
class TestDocumentRoutes:
    async def test_list_documents_empty(self, client, farmer_token):
        resp = await client.get(
            "/api/v1/documents/",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_review_queue_requires_agronomist(self, client, farmer_token):
        resp = await client.get(
            "/api/v1/documents/review-queue",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 403

    async def test_review_queue_accessible_to_agronomist(self, client, agronomist_token):
        resp = await client.get(
            "/api/v1/documents/review-queue",
            headers={"Authorization": f"Bearer {agronomist_token}"},
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestHealthRoutes:
    async def test_readiness(self, client):
        resp = await client.get("/ready")
        assert resp.status_code == 200
        assert resp.json()["ready"] is True
