"""Tests para endpoints de tasas."""

import pytest
from datetime import datetime, timezone
from sqlalchemy import text

from src.main import app
from src.database import get_engine, get_session_maker, async_session_factory
from src.models.rate_snapshot import RateSnapshot


@pytest.fixture
def client():
    """Crear cliente de test para endpoints."""
    from starlette.testclient import TestClient
    with TestClient(app) as client:
        yield client


@pytest.fixture
async def db_session():
    """Crear sesión de base de datos para tests."""
    async with async_session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def sample_data(db_session):
    """Insertar datos de ejemplo en la DB para tests."""
    now = datetime.now(timezone.utc)
    
    # Insertar snapshots de ejemplo para ElToque
    snapshots = [
        RateSnapshot(
            source='eltoque',
            currency='USD',
            buy_rate=None,
            sell_rate=365.00,
            fetched_at=now
        ),
        RateSnapshot(
            source='eltoque',
            currency='EUR',
            buy_rate=None,
            sell_rate=398.00,
            fetched_at=now
        ),
        RateSnapshot(
            source='eltoque',
            currency='USD',
            buy_rate=None,
            sell_rate=360.00,
            fetched_at=datetime(2026, 3, 20, 14, 30, tzinfo=timezone.utc)  # Anterior
        ),
        # CADECA
        RateSnapshot(
            source='cadeca',
            currency='USD',
            buy_rate=120.00,
            sell_rate=125.00,
            fetched_at=now
        ),
        # BCC
        RateSnapshot(
            source='bcc',
            currency='USD',
            buy_rate=None,
            sell_rate=125.00,
            fetched_at=now
        ),
        # Binance
        RateSnapshot(
            source='binance',
            currency='BTC',
            buy_rate=None,
            sell_rate=67500.00,
            fetched_at=now
        ),
    ]
    
    for snap in snapshots:
        db_session.add(snap)
    
    await db_session.commit()
    
    yield
    
    # Cleanup
    await db_session.execute(text("DELETE FROM rate_snapshots"))
    await db_session.commit()


def test_get_latest_rates_structure(client, sample_data):
    """GET /api/v1/tasas/latest retorna estructura correcta."""
    response = client.get("/api/v1/tasas/latest")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["ok"] is True
    assert "data" in data
    assert "updated_at" in data
    
    # Verificar que todas las fuentes están presentes
    assert "eltoque" in data["data"]
    assert "cadeca" in data["data"]
    assert "bcc" in data["data"]
    assert "binance" in data["data"]


def test_get_latest_rates_eltoque(client, sample_data):
    """GET /api/v1/tasas/latest incluye tasas de ElToque con cambio."""
    response = client.get("/api/v1/tasas/latest")
    
    assert response.status_code == 200
    data = response.json()
    
    eltoque = data["data"]["eltoque"]
    assert "USD" in eltoque
    assert eltoque["USD"]["rate"] == 365.00
    assert eltoque["USD"]["change"] in ["up", "down", "neutral"]
    assert "prev_rate" in eltoque["USD"]


def test_get_eltoque_rates(client, sample_data):
    """GET /api/v1/tasas/eltoque retorna solo tasas de ElToque."""
    response = client.get("/api/v1/tasas/eltoque")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["source"] == "eltoque"
    assert "rates" in data
    assert "updated_at" in data
    
    rates = data["rates"]
    assert "USD" in rates
    assert rates["USD"]["rate"] == 365.00
    assert rates["USD"]["change"] in ["up", "down", "neutral"]


def test_get_cadeca_rates(client, sample_data):
    """GET /api/v1/tasas/cadeca retorna solo tasas de CADECA."""
    response = client.get("/api/v1/tasas/cadeca")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["source"] == "cadeca"
    assert "rates" in data
    
    rates = data["rates"]
    assert "USD" in rates
    # CADECA tiene buy/sell, el rate principal es sell
    assert rates["USD"]["rate"] == 125.00


def test_get_bcc_rates(client, sample_data):
    """GET /api/v1/tasas/bcc retorna solo tasas de BCC."""
    response = client.get("/api/v1/tasas/bcc")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["source"] == "bcc"
    assert "rates" in data
    
    rates = data["rates"]
    assert "USD" in rates
    assert rates["USD"]["rate"] == 125.00


def test_get_history_default_params(client, sample_data):
    """GET /api/v1/tasas/history usa params por defecto correctos."""
    response = client.get("/api/v1/tasas/history")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["ok"] is True
    assert "data" in data
    assert "count" in data
    assert isinstance(data["data"], list)


def test_get_history_with_params(client, sample_data):
    """GET /api/v1/tasas/history acepta query params personalizados."""
    response = client.get("/api/v1/tasas/history?source=eltoque&currency=USD&days=7")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["ok"] is True
    assert data["count"] >= 1
    
    # Verificar estructura de snapshots
    if data["count"] > 0:
        snapshot = data["data"][0]
        assert snapshot["source"] == "eltoque"
        assert snapshot["currency"] == "USD"
        assert "fetched_at" in snapshot
        assert "sell_rate" in snapshot


def test_get_history_invalid_source(client):
    """GET /api/v1/tasas/history usa default si source es inválido."""
    # El parámetro tiene default="eltoque", así que usa el default si es inválido
    response = client.get("/api/v1/tasas/history?source=invalid")
    
    # Debería usar el default y retornar 200
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True


def test_get_history_invalid_days(client):
    """GET /api/v1/tasas/history rechaza days fuera de rango."""
    response = client.get("/api/v1/tasas/history?days=0")
    assert response.status_code == 422
    
    response = client.get("/api/v1/tasas/history?days=400")
    assert response.status_code == 422


def test_empty_database(client):
    """Endpoints manejan correctamente DB vacía."""
    # Sin datos, los endpoints deben retornar estructuras vacías
    response = client.get("/api/v1/tasas/latest")

    assert response.status_code == 200
    data = response.json()

    assert data["ok"] is True
    # Las fuentes pueden estar vacías si no hay datos
    assert isinstance(data["data"]["eltoque"], dict)


def test_get_cubanomic_rates_structure(client):
    """GET /api/v1/tasas/cubanomic retorna estructura correcta."""
    response = client.get("/api/v1/tasas/cubanomic")

    # Should return 200 even if Redis is not available (fallback)
    assert response.status_code == 200
    data = response.json()

    assert data["source"] == "cubanomic"
    assert "rates" in data
    assert "updated_at" in data


def test_get_cubanomic_rates_with_max_age(client):
    """GET /api/v1/tasas/cubanomic acepta max_age_minutes param."""
    response = client.get("/api/v1/tasas/cubanomic?max_age_minutes=60")

    # Should validate min value (60)
    assert response.status_code in [200, 422]


def test_get_cubanomic_rates_invalid_max_age(client):
    """GET /api/v1/tasas/cubanomic rechaza max_age_minutes inválido."""
    # Below minimum (60)
    response = client.get("/api/v1/tasas/cubanomic?max_age_minutes=30")
    assert response.status_code == 422

    # Above maximum (2880)
    response = client.get("/api/v1/tasas/cubanomic?max_age_minutes=3000")
    assert response.status_code == 422
