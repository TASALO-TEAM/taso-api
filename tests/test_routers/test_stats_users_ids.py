"""Tests para GET /api/v1/admin/stats/users/ids (comando /ms de taso-bot)."""

import pytest
from starlette.testclient import TestClient

from src.main import app

ADMIN_API_KEY = "your_secret_admin_key_here"


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def valid_auth_headers():
    return {"X-API-Key": ADMIN_API_KEY}


class TestUserIdsAuth:
    """El endpoint es admin-only: no debe ser accesible sin X-API-Key."""

    def test_without_auth_returns_401(self, client):
        response = client.get("/api/v1/admin/stats/users/ids")
        assert response.status_code == 401

    def test_with_invalid_auth_returns_401(self, client):
        response = client.get(
            "/api/v1/admin/stats/users/ids",
            headers={"X-API-Key": "invalid_key"},
        )
        assert response.status_code == 401


class TestUserIdsResponse:
    """Con auth válida debe devolver la forma esperada de la respuesta."""

    def test_returns_ok_and_list_shape(self, client, valid_auth_headers):
        response = client.get(
            "/api/v1/admin/stats/users/ids",
            headers=valid_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert isinstance(data["data"], list)
        # Cualquier user_id presente debe ser entero (BigInteger de Telegram)
        assert all(isinstance(uid, int) for uid in data["data"])

    def test_tracked_user_appears_in_ids(self, client, valid_auth_headers):
        # Trackear un comando crea/actualiza el BotUser correspondiente
        track_resp = client.post(
            "/api/v1/admin/stats/track",
            json={"command": "/test_ms_ids", "user_id": 999999001, "username": "ms_test_user"},
            headers=valid_auth_headers,
        )
        assert track_resp.status_code == 200

        ids_resp = client.get(
            "/api/v1/admin/stats/users/ids",
            headers=valid_auth_headers,
        )
        assert ids_resp.status_code == 200
        assert 999999001 in ids_resp.json()["data"]
