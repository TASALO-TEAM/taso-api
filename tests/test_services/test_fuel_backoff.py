"""Tests del backoff de fuel_service: si eltoque.com bloquea al scraper, no se reintenta en cada petición."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services import fuel_service

RAW_OK = {"B-94": {"range_min": 450, "range_max": 480, "primary_value": 465}}


@pytest.fixture(autouse=True)
def reset_cache():
    fuel_service._fuel_cache.update({"rates": {}, "fetched_at": None, "failed_at": None})
    yield
    fuel_service._fuel_cache.update({"rates": {}, "fetched_at": None, "failed_at": None})


@pytest.fixture
def db():
    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    result.scalars.return_value.first.return_value = None
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_scraping_fallido_no_se_repite_dentro_del_backoff(db, monkeypatch):
    calls = []

    async def blocked():
        calls.append(1)
        return None  # 403 de Cloudflare

    monkeypatch.setattr(fuel_service, "fetch_fuel", blocked)
    await fuel_service.get_fuel_rates(db)
    await fuel_service.get_fuel_rates(db)
    await fuel_service.get_fuel_rates(db)
    assert len(calls) == 1, "solo el primer intento sale a eltoque.com"


@pytest.mark.asyncio
async def test_pasado_el_backoff_se_reintenta(db, monkeypatch):
    calls = []

    async def blocked():
        calls.append(1)
        return None

    monkeypatch.setattr(fuel_service, "fetch_fuel", blocked)
    await fuel_service.get_fuel_rates(db)
    fuel_service._fuel_cache["failed_at"] = datetime.now(timezone.utc) - timedelta(minutes=fuel_service.FAIL_BACKOFF_MINUTES + 1)
    await fuel_service.get_fuel_rates(db)
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_exito_limpia_el_fallo_y_llena_la_cache(db, monkeypatch):
    async def ok():
        return RAW_OK

    monkeypatch.setattr(fuel_service, "fetch_fuel", ok)
    fuel_service._fuel_cache["failed_at"] = datetime.now(timezone.utc) - timedelta(minutes=fuel_service.FAIL_BACKOFF_MINUTES + 1)
    rates, _ = await fuel_service.get_fuel_rates(db)
    assert "B-94" in rates
    assert fuel_service._fuel_cache["failed_at"] is None
    assert fuel_service._fuel_cache["rates"] == rates


@pytest.mark.asyncio
async def test_en_backoff_se_sirve_la_cache_stale_sin_scrapear(db, monkeypatch):
    calls = []

    async def blocked():
        calls.append(1)
        return None

    monkeypatch.setattr(fuel_service, "fetch_fuel", blocked)
    old = datetime.now(timezone.utc) - timedelta(hours=3)
    fuel_service._fuel_cache.update({"rates": {"B-94": {"rate": 1}}, "fetched_at": old, "failed_at": datetime.now(timezone.utc)})
    rates, updated = await fuel_service.get_fuel_rates(db)
    assert rates == {"B-94": {"rate": 1}}
    assert updated == old, "la hora real de los datos, para que los clientes avisen de que están viejos"
    assert calls == []


def test_in_backoff_limites():
    now = datetime.now(timezone.utc)
    assert fuel_service._in_backoff(None, now) is False
    assert fuel_service._in_backoff(now - timedelta(minutes=1), now) is True
    assert fuel_service._in_backoff(now - timedelta(minutes=fuel_service.FAIL_BACKOFF_MINUTES + 1), now) is False
