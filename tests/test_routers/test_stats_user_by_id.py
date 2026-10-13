"""Tests para GET /api/v1/admin/stats/users/{user_id} (estadísticas por usuario)."""

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


def _track(client, headers, user_id, command, source=None, success=True, username="stats_user"):
    resp = client.post(
        "/api/v1/admin/stats/track",
        json={
            "command": command,
            "user_id": user_id,
            "username": username,
            "source": source,
            "success": success,
        },
        headers=headers,
    )
    assert resp.status_code == 200


class TestUserStatsAuth:
    """Es admin-only: sin X-API-Key válida no se puede consultar."""

    def test_without_auth_returns_401(self, client):
        assert client.get("/api/v1/admin/stats/users/999999100").status_code == 401

    def test_with_invalid_auth_returns_401(self, client):
        response = client.get(
            "/api/v1/admin/stats/users/999999100",
            headers={"X-API-Key": "invalid_key"},
        )
        assert response.status_code == 401


class TestUserStatsResponse:
    def test_unknown_user_returns_empty_found_false(self, client, valid_auth_headers):
        response = client.get(
            "/api/v1/admin/stats/users/999999199", headers=valid_auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["found"] is False
        assert data["total_commands"] == 0
        assert data["success_rate"] == 0.0
        assert data["by_command"] == []
        assert data["by_source"] == []
        assert data["first_seen"] is None
        assert data["window"] == "7d"

    def test_aggregates_only_that_user(self, client, valid_auth_headers):
        uid, other = 999999101, 999999102
        _track(client, valid_auth_headers, uid, "/status_u1", source="eltoque")
        _track(client, valid_auth_headers, uid, "/status_u1", source="eltoque")
        _track(client, valid_auth_headers, uid, "/status_u2", source="bcc", success=False)
        _track(client, valid_auth_headers, other, "/status_u1", source="cadeca", username="otro")

        response = client.get(
            f"/api/v1/admin/stats/users/{uid}?window=30d", headers=valid_auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["found"] is True
        assert data["user_id"] == uid
        assert data["window"] == "30d"
        assert data["total_commands"] == 3
        assert data["successful"] == 2
        assert data["failed"] == 1
        assert data["success_rate"] == pytest.approx(66.7, abs=0.05)
        assert data["by_command"][0] == {"name": "/status_u1", "count": 2}
        assert {"name": "/status_u2", "count": 1} in data["by_command"]
        sources = {item["name"]: item["count"] for item in data["by_source"]}
        assert sources == {"eltoque": 2, "bcc": 1}  # nada de «cadeca» (es de otro usuario)
        assert data["first_seen"] is not None
        assert data["last_seen"] is not None
        assert data["total_commands_all_time"] >= 3

    def test_user_without_source_has_no_sources(self, client, valid_auth_headers):
        uid = 999999103
        _track(client, valid_auth_headers, uid, "/status_u3")
        data = client.get(
            f"/api/v1/admin/stats/users/{uid}", headers=valid_auth_headers
        ).json()
        assert data["total_commands"] == 1
        assert data["by_source"] == []


class TestUserStatsValidation:
    def test_invalid_window_is_rejected(self, client, valid_auth_headers):
        response = client.get(
            "/api/v1/admin/stats/users/999999101?window=1y", headers=valid_auth_headers
        )
        assert response.status_code == 422

    def test_non_numeric_user_id_is_rejected(self, client, valid_auth_headers):
        response = client.get(
            "/api/v1/admin/stats/users/abc", headers=valid_auth_headers
        )
        assert response.status_code == 422

    def test_fixed_routes_still_win(self, client, valid_auth_headers):
        """/users/ids y /users/lookup no se confunden con /users/{user_id}."""
        assert client.get(
            "/api/v1/admin/stats/users/ids", headers=valid_auth_headers
        ).status_code == 200
        assert client.get(
            "/api/v1/admin/stats/users/lookup?username=nadie_999",
            headers=valid_auth_headers,
        ).status_code == 200
