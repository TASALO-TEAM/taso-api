"""Tests para /api/v1/tickets (creación, listado, actualización)."""

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


class TestTicketsAuth:
    """Todos los endpoints de tickets requieren X-API-Key (mismo criterio que /alerts)."""

    def test_create_without_auth_returns_401(self, client):
        response = client.post(
            "/api/v1/tickets",
            json={"user_id": 1, "kind": "bug", "message": "algo no anda"},
        )
        assert response.status_code == 401

    def test_list_without_auth_returns_401(self, client):
        response = client.get("/api/v1/tickets")
        assert response.status_code == 401


class TestTicketsCrudFlow:
    """Flujo completo create -> list -> update."""

    def test_full_flow(self, client, valid_auth_headers):
        create_resp = client.post(
            "/api/v1/tickets",
            json={
                "user_id": 999999002,
                "username": "tkt_test_user",
                "kind": "bug",
                "message": "El comando /p no responde con HIVE",
            },
            headers=valid_auth_headers,
        )
        assert create_resp.status_code == 200
        created = create_resp.json()
        assert created["ok"] is True
        assert created["data"]["status"] == "open"
        ticket_id = created["data"]["id"]

        # Aparece en el listado
        list_resp = client.get(
            "/api/v1/tickets", params={"kind": "bug"}, headers=valid_auth_headers,
        )
        ids = [t["id"] for t in list_resp.json()["data"]]
        assert ticket_id in ids

        # Tomar el ticket → pasa a in_progress automáticamente
        claim_resp = client.patch(
            f"/api/v1/tickets/{ticket_id}",
            json={"claimed_by": 42},
            headers=valid_auth_headers,
        )
        assert claim_resp.status_code == 200
        assert claim_resp.json()["data"]["status"] == "in_progress"
        assert claim_resp.json()["data"]["claimed_by"] == 42

        # Marcar resuelto
        resolve_resp = client.patch(
            f"/api/v1/tickets/{ticket_id}",
            json={"status": "resolved"},
            headers=valid_auth_headers,
        )
        assert resolve_resp.status_code == 200
        assert resolve_resp.json()["data"]["status"] == "resolved"

    def test_create_invalid_kind_returns_422(self, client, valid_auth_headers):
        response = client.post(
            "/api/v1/tickets",
            json={"user_id": 1, "kind": "otra_cosa", "message": "mensaje de prueba"},
            headers=valid_auth_headers,
        )
        assert response.status_code == 422

    def test_update_nonexistent_returns_404(self, client, valid_auth_headers):
        response = client.patch(
            "/api/v1/tickets/999999999",
            json={"status": "closed"},
            headers=valid_auth_headers,
        )
        assert response.status_code == 404
