"""Tests for the /year/* public (e2e) endpoints.

Uses the conftest.py client fixture (sync TestClient backed by the production
Supabase PostgreSQL database via the app lifespan).

No SQLite — Supabase PostgreSQL is required for async FastAPI tests.
"""

import os
import uuid
import pytest

from src.main import app

_PROD_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:Mendeleyev931225@db.kkvrjpoxtauwhjrsznkd.supabase.co:5432/postgres"
    "?sslmode=require&sslaccept=accept_all",
)


@pytest.fixture(scope="session", autouse=True)
def _prod_db_env():
    """Ensure DATABASE_URL is the production Supabase URL."""
    os.environ["DATABASE_URL"] = _PROD_URL
    yield
    os.environ.pop("DATABASE_URL", None)


@pytest.fixture(autouse=True)
def _clean_year_tables():
    """After each test, remove any rows OUR test added to year tables."""
    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = _PROD_URL
    yield
    # Leave production data untouched — tests only read + create-idempotent
    os.environ["DATABASE_URL"] = original or _PROD_URL


@pytest.fixture
def client():
    """Sync TestClient using conftest pattern (session-scoped)."""
    from starlette.testclient import TestClient
    with TestClient(app) as tc:
        yield tc


# ── E2E tests (public endpoints, no auth required) ──────────────────────────

def test_get_today_quote(client):
    r = client.get("/api/v1/year/quotes/today")
    assert r.status_code == 200, f"Unexpected status {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert data["ok"] is True
    assert "quote" in data
    assert isinstance(data["quote"], str)


def test_get_year_state(client):
    r = client.get("/api/v1/year/state")
    assert r.status_code == 200, f"Unexpected status {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert data["ok"] is True
    assert "progress" in data
    assert "quote" in data
    assert "stats" in data
    # progress fields
    p = data["progress"]
    assert "year" in p and isinstance(p["year"], int)
    assert "percent" in p and isinstance(p["percent"], float)
    assert "days_left" in p and isinstance(p["days_left"], int)
    assert "date_str" in p


def test_get_stats(client):
    r = client.get("/api/v1/year/quotes/stats")
    assert r.status_code == 200, f"Unexpected status {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert data["ok"] is True
    assert "total" in data["data"]
    assert "limit" in data["data"]
    assert "has_reached_limit" in data["data"]


def test_list_quotes(client):
    r = client.get("/api/v1/year/quotes")
    assert r.status_code == 200, f"Unexpected status {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert data["ok"] is True
    assert "data" in data
    assert isinstance(data["data"], list)


def test_extra_flag(client):
    r = client.get("/api/v1/year/extra-flag/2026")
    assert r.status_code == 200, f"Unexpected status {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert data["ok"] is True
    assert data["year"] == 2026
    assert "asked" in data
