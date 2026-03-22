"""Tests para la aplicación FastAPI y endpoints."""

import pytest
from starlette.testclient import TestClient

from src.main import app


@pytest.fixture
def client():
    """Crear cliente de test sincrónico con lifespan manager."""
    with TestClient(app) as client:
        yield client


def test_health_endpoint(client):
    """GET /api/v1/health retorna estado correcto."""
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()

    assert data["ok"] is True
    assert "version" in data
    assert data["version"] == "1.5.0"
    assert "db" in data
    assert data["db"] in ["connected", "disconnected"]


def test_docs_available(client):
    """Swagger docs están disponibles."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_openapi_json(client):
    """OpenAPI spec está disponible."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    data = response.json()
    assert "openapi" in data
    assert data["info"]["title"] == "TASALO API"
    assert data["info"]["version"] == "1.5.0"
