"""Tests para GET /api/v1/admin/stats/users/lookup (comando /ms <@usuario>)."""

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


class TestUserLookupAuth:
    """El endpoint es admin-only: no debe ser accesible sin X-API-Key."""

    def test_without_auth_returns_401(self, client):
        response = client.get("/api/v1/admin/stats/users/lookup?username=pepito")
        assert response.status_code == 401

    def test_with_invalid_auth_returns_401(self, client):
        response = client.get(
            "/api/v1/admin/stats/users/lookup?username=pepito",
            headers={"X-API-Key": "invalid_key"},
        )
        assert response.status_code == 401


class TestUserLookupResponse:
    """Con auth válida debe encontrar el user_id o devolver data=None."""

    def test_username_not_found_returns_none(self, client, valid_auth_headers):
        response = client.get(
            "/api/v1/admin/stats/users/lookup?username=usuario_que_no_existe_999",
            headers=valid_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["data"] is None

    def test_tracked_user_is_found_by_username(self, client, valid_auth_headers):
        track_resp = client.post(
            "/api/v1/admin/stats/track",
            json={"command": "/test_ms_lookup", "user_id": 999999003, "username": "lookup_test_user"},
            headers=valid_auth_headers,
        )
        assert track_resp.status_code == 200

        lookup_resp = client.get(
            "/api/v1/admin/stats/users/lookup?username=lookup_test_user",
            headers=valid_auth_headers,
        )
        assert lookup_resp.status_code == 200
        data = lookup_resp.json()
        assert data["ok"] is True
        assert data["data"]["user_id"] == 999999003

    def test_lookup_is_case_insensitive_and_accepts_at_prefix(self, client, valid_auth_headers):
        client.post(
            "/api/v1/admin/stats/track",
            json={"command": "/test_ms_lookup", "user_id": 999999004, "username": "MixedCase_User"},
            headers=valid_auth_headers,
        )

        lookup_resp = client.get(
            "/api/v1/admin/stats/users/lookup?username=@mixedcase_user",
            headers=valid_auth_headers,
        )
        assert lookup_resp.status_code == 200
        assert lookup_resp.json()["data"]["user_id"] == 999999004
