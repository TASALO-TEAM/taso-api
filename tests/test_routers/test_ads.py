"""Tests para endpoints de /api/v1/ads (públicos y admin)."""

import pytest
from starlette.testclient import TestClient

from src.main import app

ADMIN_API_KEY = "your_secret_admin_key_here"
INVALID_API_KEY = "invalid_key"


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def valid_auth_headers():
    return {"X-API-Key": ADMIN_API_KEY}


@pytest.fixture
def no_auth_headers():
    return {}


class TestAdsAuth:
    """Los endpoints admin deben exigir X-API-Key; los públicos no."""

    def test_admin_list_without_auth_returns_401(self, client, no_auth_headers):
        response = client.get("/api/v1/ads", headers=no_auth_headers)
        assert response.status_code == 401

    def test_admin_create_without_auth_returns_401(self, client, no_auth_headers):
        response = client.post("/api/v1/ads", json={"text": "x"}, headers=no_auth_headers)
        assert response.status_code == 401

    def test_public_active_without_auth_returns_200(self, client, no_auth_headers):
        response = client.get("/api/v1/ads/active", headers=no_auth_headers)
        assert response.status_code == 200

    def test_public_random_without_auth_returns_200(self, client, no_auth_headers):
        response = client.get("/api/v1/ads/random", headers=no_auth_headers)
        assert response.status_code == 200


class TestAdsCrudFlow:
    """Flujo completo create -> list -> update -> public visibility -> delete."""

    def test_full_crud_lifecycle(self, client, valid_auth_headers, no_auth_headers):
        # Crear
        create_resp = client.post(
            "/api/v1/ads",
            json={"text": "Anuncio de prueba automatizada", "is_sponsored": False, "weight": 1},
            headers=valid_auth_headers,
        )
        assert create_resp.status_code == 200
        created = create_resp.json()
        assert created["ok"] is True
        ad_id = created["data"]["id"]

        try:
            # Aparece en el listado admin
            list_resp = client.get("/api/v1/ads", headers=valid_auth_headers)
            ids = [a["id"] for a in list_resp.json()["data"]]
            assert ad_id in ids

            # Aparece en el endpoint público /active (sin campos sensibles)
            active_resp = client.get("/api/v1/ads/active", headers=no_auth_headers)
            active_ids = [a["id"] for a in active_resp.json()["data"]]
            assert ad_id in active_ids
            active_item = next(a for a in active_resp.json()["data"] if a["id"] == ad_id)
            assert "created_by" not in active_item
            assert "created_at" not in active_item

            # Editar: marcar como patrocinado
            patch_resp = client.patch(
                f"/api/v1/ads/{ad_id}",
                json={"is_sponsored": True},
                headers=valid_auth_headers,
            )
            assert patch_resp.status_code == 200
            assert patch_resp.json()["data"]["is_sponsored"] is True

            # Desactivar: ya no debe salir en /active
            client.patch(f"/api/v1/ads/{ad_id}", json={"is_active": False}, headers=valid_auth_headers)
            active_resp2 = client.get("/api/v1/ads/active", headers=no_auth_headers)
            active_ids2 = [a["id"] for a in active_resp2.json()["data"]]
            assert ad_id not in active_ids2
        finally:
            # Limpieza: borrar el anuncio de prueba
            del_resp = client.delete(f"/api/v1/ads/{ad_id}", headers=valid_auth_headers)
            assert del_resp.status_code == 200

    def test_update_nonexistent_returns_404(self, client, valid_auth_headers):
        response = client.patch(
            "/api/v1/ads/999999", json={"text": "x"}, headers=valid_auth_headers
        )
        assert response.status_code == 404

    def test_delete_nonexistent_returns_404(self, client, valid_auth_headers):
        response = client.delete("/api/v1/ads/999999", headers=valid_auth_headers)
        assert response.status_code == 404

    def test_create_rejects_empty_text(self, client, valid_auth_headers):
        response = client.post("/api/v1/ads", json={"text": ""}, headers=valid_auth_headers)
        assert response.status_code == 422

    def test_create_rejects_text_over_300_chars(self, client, valid_auth_headers):
        response = client.post(
            "/api/v1/ads", json={"text": "x" * 301}, headers=valid_auth_headers
        )
        assert response.status_code == 422
