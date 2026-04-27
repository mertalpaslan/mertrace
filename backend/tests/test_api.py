import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "app" in data


@pytest.mark.asyncio
async def test_list_projects_empty(client: AsyncClient):
    response = await client.get("/api/projects/")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_project_missing_url(client: AsyncClient):
    response = await client.post(
        "/api/projects/",
        json={"name": "test-project"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_project_with_url(client: AsyncClient):
    with patch(
        "app.api.routes.projects.run_pipeline",
        new_callable=AsyncMock,
    ):
        response = await client.post(
            "/api/projects/",
            json={"name": "tiny", "url": "https://github.com/pallets/click"},
        )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["name"] == "tiny"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_project_not_found(client: AsyncClient):
    response = await client.get("/api/projects/nonexistent-id")
    assert response.status_code == 404
