"""Tests para /api/v1/app/messages (mensajes de la app Android: público y admin)
y para el campo sources_updated_at de /api/v1/tasas/latest."""

from datetime import datetime, timezone

import pytest
from starlette.testclient import TestClient

from src.main import app
from src.routers.rates import _latest_fetched_at

ADMIN_API_KEY = "your_secret_admin_key_here"


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def valid_auth_headers():
    return {"X-API-Key": ADMIN_API_KEY}


class TestAppMessagesAuth:
    """Admin exige X-API-Key; el listado público no."""

    def test_admin_list_without_auth_returns_401(self, client):
        assert client.get("/api/v1/app/messages/all").status_code == 401

    def test_admin_create_without_auth_returns_401(self, client):
        response = client.post("/api/v1/app/messages", json={"title": "x", "body": "y"})
        assert response.status_code == 401

    def test_admin_patch_and_delete_without_auth_return_401(self, client):
        assert client.patch("/api/v1/app/messages/1", json={"is_active": False}).status_code == 401
        assert client.delete("/api/v1/app/messages/1").status_code == 401

    def test_public_list_without_auth_returns_200(self, client):
        response = client.get("/api/v1/app/messages")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert isinstance(body["data"], list)


class TestAppMessagesValidation:
    def test_limit_must_be_between_1_and_20(self, client):
        assert client.get("/api/v1/app/messages?limit=0").status_code == 422
        assert client.get("/api/v1/app/messages?limit=21").status_code == 422
        assert client.get("/api/v1/app/messages?limit=20").status_code == 200

    def test_since_id_cannot_be_negative(self, client):
        assert client.get("/api/v1/app/messages?since_id=-1").status_code == 422

    def test_body_over_telegram_limit_is_rejected(self, client, valid_auth_headers):
        response = client.post(
            "/api/v1/app/messages",
            json={"title": "t", "body": "x" * 4097},
            headers=valid_auth_headers,
        )
        assert response.status_code == 422

    def test_unknown_format_is_rejected(self, client, valid_auth_headers):
        response = client.post(
            "/api/v1/app/messages",
            json={"title": "t", "body": "b", "format": "html"},
            headers=valid_auth_headers,
        )
        assert response.status_code == 422


class TestAppMessagesLifecycle:
    """create -> visible en público -> since_id -> desactivar -> borrar."""

    def test_full_lifecycle(self, client, valid_auth_headers):
        created = client.post(
            "/api/v1/app/messages",
            json={"title": "Mensaje de prueba", "body": "*Hola* desde los tests", "format": "telegram", "created_by": 123},
            headers=valid_auth_headers,
        )
        assert created.status_code == 200
        data = created.json()["data"]
        message_id = data["id"]
        assert data["format"] == "telegram"
        assert data["is_active"] is True

        try:
            # Aparece en el listado público, sin created_by
            public = client.get("/api/v1/app/messages?limit=20").json()["data"]
            mine = next(m for m in public if m["id"] == message_id)
            assert mine["title"] == "Mensaje de prueba"
            assert mine["body"] == "*Hola* desde los tests"
            assert "created_by" not in mine
            assert "is_active" not in mine

            # since_id = su propio id => no vuelve a aparecer
            newer = client.get(f"/api/v1/app/messages?since_id={message_id}").json()["data"]
            assert all(m["id"] != message_id for m in newer)

            # Los más nuevos van primero
            ids = [m["id"] for m in public]
            assert ids == sorted(ids, reverse=True)

            # Desactivar: sale del público pero sigue en el listado admin
            patched = client.patch(
                f"/api/v1/app/messages/{message_id}", json={"is_active": False}, headers=valid_auth_headers
            )
            assert patched.status_code == 200
            assert patched.json()["data"]["is_active"] is False
            public_after = client.get("/api/v1/app/messages?limit=20").json()["data"]
            assert all(m["id"] != message_id for m in public_after)
            admin_list = client.get("/api/v1/app/messages/all", headers=valid_auth_headers).json()["data"]
            assert any(m["id"] == message_id for m in admin_list)
        finally:
            deleted = client.delete(f"/api/v1/app/messages/{message_id}", headers=valid_auth_headers)
            assert deleted.status_code == 200

        # Ya no existe
        again = client.delete(f"/api/v1/app/messages/{message_id}", headers=valid_auth_headers)
        assert again.status_code == 404

    def test_patch_unknown_id_returns_404(self, client, valid_auth_headers):
        response = client.patch(
            "/api/v1/app/messages/999999999", json={"title": "x"}, headers=valid_auth_headers
        )
        assert response.status_code == 404


class TestLatestSourcesUpdatedAt:
    """El campo nuevo de /tasas/latest es aditivo y refleja la hora real de cada fuente."""

    def test_helper_picks_the_most_recent_fetched_at(self):
        rates = {
            "USD": {"rate": 1.0, "fetched_at": "2026-10-01T10:00:00+00:00"},
            "EUR": {"rate": 2.0, "fetched_at": "2026-10-01T10:05:00+00:00"},
        }
        assert _latest_fetched_at(rates) == datetime(2026, 10, 1, 10, 5, tzinfo=timezone.utc)

    def test_helper_treats_naive_timestamps_as_utc(self):
        rates = {"USD": {"fetched_at": "2026-10-01T10:00:00"}}
        assert _latest_fetched_at(rates) == datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)

    def test_helper_returns_none_without_usable_data(self):
        assert _latest_fetched_at({}) is None
        assert _latest_fetched_at({"USD": {"rate": 1.0}}) is None
        assert _latest_fetched_at({"USD": {"fetched_at": "no-es-fecha"}}) is None
        assert _latest_fetched_at({"USD": {"fetched_at": None}}) is None

    def test_latest_endpoint_keeps_updated_at_and_adds_the_new_field(self, client):
        body = client.get("/api/v1/tasas/latest").json()
        assert body["ok"] is True
        assert "updated_at" in body  # sin cambios para los consumidores actuales
        assert isinstance(body["sources_updated_at"], dict)
