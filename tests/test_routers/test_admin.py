"""Tests para endpoints admin."""

import pytest
from starlette.testclient import TestClient

from src.main import app


# Constants - Must match .env file
ADMIN_API_KEY = "your_secret_admin_key_here"
INVALID_API_KEY = "invalid_key"


@pytest.fixture
def client():
    """Crear cliente de test sincrónico con lifespan manager."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def valid_auth_headers():
    """Headers con API key válida para tests (usa el default 'changeme')."""
    return {"X-API-Key": ADMIN_API_KEY}


@pytest.fixture
def invalid_auth_headers():
    """Headers con API key inválida para tests."""
    return {"X-API-Key": INVALID_API_KEY}


@pytest.fixture
def no_auth_headers():
    """Headers sin autenticación."""
    return {}


class TestAdminAuth:
    """Tests para autenticación en endpoints admin."""

    def test_admin_endpoint_without_auth_returns_401(
        self,
        client: TestClient,
        no_auth_headers: dict
    ):
        """Endpoint admin sin auth debe retornar 401."""
        response = client.get("/api/v1/admin/status", headers=no_auth_headers)

        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert "X-API-Key" in data["error"]["message"]

    def test_admin_endpoint_with_invalid_auth_returns_401(
        self,
        client: TestClient,
        invalid_auth_headers: dict
    ):
        """Endpoint admin con API key inválida debe retornar 401."""
        response = client.get("/api/v1/admin/status", headers=invalid_auth_headers)

        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert "API key" in data["error"]["message"]


class TestAdminRefreshEndpoint:
    """Tests para POST /api/v1/admin/refresh."""

    def test_refresh_without_auth_returns_401(
        self,
        client: TestClient,
        no_auth_headers: dict
    ):
        """Refresh sin auth debe retornar 401."""
        response = client.post("/api/v1/admin/refresh", headers=no_auth_headers)
        
        assert response.status_code == 401

    def test_refresh_with_valid_auth_returns_results(
        self,
        client: TestClient,
        valid_auth_headers: dict
    ):
        """Refresh con auth válida debe retornar resultados."""
        response = client.post("/api/v1/admin/refresh", headers=valid_auth_headers)
        
        # Verificar estructura de respuesta
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "data" in data
        assert "results" in data["data"]
        assert "completed_at" in data


class TestAdminStatusEndpoint:
    """Tests para GET /api/v1/admin/status."""

    def test_status_without_auth_returns_401(
        self,
        client: TestClient,
        no_auth_headers: dict
    ):
        """Status sin auth debe retornar 401."""
        response = client.get("/api/v1/admin/status", headers=no_auth_headers)
        
        assert response.status_code == 401

    def test_status_with_valid_auth_returns_scheduler_info(
        self,
        client: TestClient,
        valid_auth_headers: dict
    ):
        """Status con auth válida debe retornar información del scheduler."""
        response = client.get("/api/v1/admin/status", headers=valid_auth_headers)
        
        # Verificar estructura de respuesta
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "scheduler" in data
        assert "updated_at" in data
        
        # Verificar campos del scheduler
        scheduler = data["scheduler"]
        assert "error_count" in scheduler
        assert "updated_at" in scheduler
