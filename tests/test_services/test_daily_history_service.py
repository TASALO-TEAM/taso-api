"""Tests del historial diario (un precio por fecha de Cuba, lectura más cercana a las 7:00)."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient

from src.main import app
from src.models.rate_snapshot import RateSnapshot
from src.services import history_service
from src.services.history_service import reduce_daily, snapshot_rate

UTC = timezone.utc


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _limpiar_cache():
    history_service.clear_cache()
    yield
    history_service.clear_cache()


class TestReduceDaily:
    def test_elige_la_lectura_mas_cercana_a_las_7_de_cuba(self):
        # Octubre: Cuba en horario de verano (UTC-4) -> las 7:00 son las 11:00 UTC.
        rows = [
            (utc(2026, 10, 8, 10, 0), 500.0),
            (utc(2026, 10, 8, 11, 20), 510.0),
            (utc(2026, 10, 8, 20, 0), 520.0),
        ]
        assert reduce_daily(rows) == [(date(2026, 10, 8), 510.0)]

    def test_agrupa_por_fecha_local_de_cuba(self):
        # 03:30 UTC del 8 son las 23:30 del 7 en Cuba: cuenta para el día 7.
        rows = [(utc(2026, 10, 8, 3, 30), 505.0), (utc(2026, 10, 8, 11, 0), 510.0)]
        assert reduce_daily(rows) == [(date(2026, 10, 7), 505.0), (date(2026, 10, 8), 510.0)]

    def test_en_invierno_las_7_son_las_12_utc(self):
        rows = [(utc(2026, 1, 15, 11, 0), 400.0), (utc(2026, 1, 15, 12, 10), 410.0)]
        assert reduce_daily(rows) == [(date(2026, 1, 15), 410.0)]

    def test_fecha_sin_zona_se_toma_como_utc(self):
        rows = [(datetime(2026, 10, 8, 11, 0), 510.0)]
        assert reduce_daily(rows) == [(date(2026, 10, 8), 510.0)]

    def test_sin_lecturas_no_hay_puntos(self):
        assert reduce_daily([]) == []


class TestSnapshotRate:
    def test_qvapay_es_el_promedio_de_compra_y_venta(self):
        assert snapshot_rate("qvapay", 530, 540) == 535.0
        assert snapshot_rate("qvapay", None, 541) == 541.0
        assert snapshot_rate("qvapay", 530, None) == 530.0

    def test_otras_fuentes_usan_la_venta(self):
        assert snapshot_rate("eltoque", None, 517.26) == 517.26
        assert snapshot_rate("cadeca", 515, 525) == 525.0
        assert snapshot_rate("bcc", 514, None) == 514.0

    def test_valores_vacios_o_cero_se_descartan(self):
        assert snapshot_rate("eltoque", None, None) is None
        assert snapshot_rate("eltoque", None, 0) is None


def _snap(source, currency, buy, sell, when):
    return RateSnapshot(source=source, currency=currency, buy_rate=buy, sell_rate=sell, fetched_at=when)


@pytest.mark.asyncio
async def test_get_daily_deja_huecos_sin_inventar_dias(db_session):
    db_session.add_all(
        [
            _snap("eltoque", "USD", None, 500, utc(2026, 10, 8, 10, 0)),
            _snap("eltoque", "USD", None, 510, utc(2026, 10, 8, 11, 20)),
            _snap("eltoque", "USD", None, 490, utc(2026, 10, 7, 3, 30)),  # 23:30 del día 6 en Cuba
            _snap("eltoque", "USD", None, 505, utc(2026, 10, 4, 11, 0)),
            _snap("eltoque", "USD", None, 100, utc(2026, 8, 1, 11, 0)),  # fuera de la ventana
            _snap("eltoque", "EUR", None, 999, utc(2026, 10, 8, 11, 0)),  # otra moneda
        ]
    )
    await db_session.commit()

    points = await history_service.get_daily(db_session, "eltoque", "USD", 7, now=utc(2026, 10, 8, 15, 0))

    assert points == [(date(2026, 10, 4), 505.0), (date(2026, 10, 6), 490.0), (date(2026, 10, 8), 510.0)]


@pytest.mark.asyncio
async def test_get_daily_con_historial_corto_devuelve_pocos_puntos(db_session):
    db_session.add(_snap("qvapay", "CUP", 530, 540, utc(2026, 10, 8, 11, 0)))
    await db_session.commit()

    points = await history_service.get_daily(db_session, "qvapay", "CUP", 180, now=utc(2026, 10, 8, 15, 0))

    assert points == [(date(2026, 10, 8), 535.0)]
    assert await history_service.get_daily(db_session, "qvapay", "MLC", 180, now=utc(2026, 10, 8, 15, 0)) == []


@pytest.mark.asyncio
async def test_get_summary_agrupa_por_fuente_y_moneda(db_session):
    db_session.add_all(
        [
            _snap("eltoque", "USD", None, 510, utc(2026, 10, 8, 11, 0)),
            _snap("eltoque", "CUP", None, 1, utc(2026, 10, 8, 11, 0)),  # CUP no cuenta fuera de QvaPay
            _snap("cadeca", "USD", 515, 525, utc(2026, 10, 8, 11, 0)),
            _snap("qvapay", "CUP", 530, 540, utc(2026, 10, 8, 11, 0)),
            _snap("binance", "BTC", None, 95000, utc(2026, 10, 8, 11, 0)),  # no está en el resumen
        ]
    )
    await db_session.commit()

    data = await history_service.get_summary(db_session, 30, now=utc(2026, 10, 8, 15, 0))

    assert data == {
        "eltoque": {"USD": [(date(2026, 10, 8), 510.0)]},
        "cadeca": {"USD": [(date(2026, 10, 8), 525.0)]},
        "qvapay": {"CUP": [(date(2026, 10, 8), 535.0)]},
    }


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


class TestEndpoints:
    def test_daily_devuelve_el_contrato(self, client):
        fake = AsyncMock(return_value=[(date(2026, 10, 7), 515.0), (date(2026, 10, 8), 520.5)])
        with patch("src.routers.rates.history_service.get_daily", new=fake):
            response = client.get("/api/v1/tasas/history/daily?source=eltoque&currency=usd&days=30")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["source"] == "eltoque"
        assert body["currency"] == "USD"
        assert body["tz"] == "America/Havana"
        assert body["data"] == [{"date": "2026-10-07", "rate": 515.0}, {"date": "2026-10-08", "rate": 520.5}]
        assert fake.await_args.args[1:] == ("eltoque", "USD", 30)

    def test_daily_rechaza_fuente_o_dias_invalidos(self, client):
        assert client.get("/api/v1/tasas/history/daily?source=nada").status_code == 422
        assert client.get("/api/v1/tasas/history/daily?days=0").status_code == 422
        assert client.get("/api/v1/tasas/history/daily?days=366").status_code == 422

    def test_summary_devuelve_el_contrato(self, client):
        fake = AsyncMock(return_value={"eltoque": {"USD": [(date(2026, 10, 8), 510.0)]}})
        with patch("src.routers.rates.history_service.get_summary", new=fake):
            response = client.get("/api/v1/tasas/history/summary?days=30")
        assert response.status_code == 200
        body = response.json()
        assert body["days"] == 30
        assert body["data"] == {"eltoque": {"USD": [{"date": "2026-10-08", "rate": 510.0}]}}

    def test_las_rutas_viejas_siguen_funcionando(self, client):
        # /history/local y /history/cubanomic no deben quedar tapadas por las rutas nuevas.
        assert client.get("/api/v1/tasas/history/local?days=1").status_code == 200
