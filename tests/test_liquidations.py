"""Tests de liquidaciones agregadas (taso-bot M3a).

Se guardan cubos de 1 minuto por exchange/simbolo/lado. El colector websocket
y sus parsers van en otro paso (hace falta verificar muestras reales primero).
"""

from datetime import datetime, timedelta, timezone

import pytest
from starlette.testclient import TestClient

from src.main import app
from src.services import liquidations as liq

NOW = datetime(2026, 11, 25, 18, 0, 30, tzinfo=timezone.utc)


def _ev(minutes_ago=0, exchange="binance", symbol="BTC", side="long", usd=1000.0):
    return liq.LiqEvent(
        ts=NOW - timedelta(minutes=minutes_ago),
        exchange=exchange, symbol=symbol, side=side, notional_usd=usd,
    )


class TestRecord:
    async def test_acumula_eventos_del_mismo_minuto_y_clave(self, db_session):
        await liq.record_events(db_session, [_ev(usd=100), _ev(usd=250)])

        rows = await liq.get_liquidations(db_session, "5m", "symbol", now=NOW)

        assert [(r.key, r.long_usd, r.short_usd) for r in rows.data] == [("BTC", 350.0, 0.0)]

    async def test_un_segundo_volcado_suma_sobre_el_cubo_existente(self, db_session):
        await liq.record_events(db_session, [_ev(usd=100)])
        await liq.record_events(db_session, [_ev(usd=50)])

        rows = await liq.get_liquidations(db_session, "5m", "symbol", now=NOW)

        assert rows.data[0].long_usd == 150.0

    async def test_rechaza_un_lado_invalido(self, db_session):
        with pytest.raises(ValueError):
            await liq.record_events(db_session, [_ev(side="buy")])

    async def test_lista_vacia_no_hace_nada(self, db_session):
        await liq.record_events(db_session, [])
        rows = await liq.get_liquidations(db_session, "5m", "symbol", now=NOW)
        assert rows.data == [] and rows.coverage_from is None


class TestQuery:
    async def test_separa_longs_y_shorts_y_ordena_por_total(self, db_session):
        await liq.record_events(db_session, [
            _ev(symbol="ETH", side="long", usd=100),
            _ev(symbol="BTC", side="long", usd=300),
            _ev(symbol="BTC", side="short", usd=200),
        ])

        rows = await liq.get_liquidations(db_session, "1h", "symbol", now=NOW)

        assert [(r.key, r.long_usd, r.short_usd, r.total_usd) for r in rows.data] == [
            ("BTC", 300.0, 200.0, 500.0),
            ("ETH", 100.0, 0.0, 100.0),
        ]

    async def test_la_ventana_excluye_lo_anterior(self, db_session):
        await liq.record_events(db_session, [_ev(minutes_ago=2, usd=10), _ev(minutes_ago=30, usd=99)])

        cinco = await liq.get_liquidations(db_session, "5m", "symbol", now=NOW)
        hora = await liq.get_liquidations(db_session, "1h", "symbol", now=NOW)

        assert cinco.data[0].total_usd == 10.0
        assert hora.data[0].total_usd == 109.0

    async def test_agrupa_por_exchange(self, db_session):
        await liq.record_events(db_session, [
            _ev(exchange="binance", usd=100), _ev(exchange="okx", symbol="ETH", usd=40),
        ])

        rows = await liq.get_liquidations(db_session, "1h", "exchange", now=NOW)

        assert {r.key: r.total_usd for r in rows.data} == {"binance": 100.0, "okx": 40.0}

    async def test_coverage_from_es_el_dato_mas_antiguo_guardado(self, db_session):
        await liq.record_events(db_session, [_ev(minutes_ago=40), _ev(minutes_ago=1)])

        rows = await liq.get_liquidations(db_session, "5m", "symbol", now=NOW)

        assert rows.coverage_from == (NOW - timedelta(minutes=40)).replace(second=0, microsecond=0)

    async def test_ventana_invalida_lanza_valueerror(self, db_session):
        with pytest.raises(ValueError):
            await liq.get_liquidations(db_session, "2h", "symbol", now=NOW)


class TestPurge:
    async def test_borra_solo_lo_anterior_a_25_horas(self, db_session):
        await liq.record_events(db_session, [_ev(minutes_ago=26 * 60, usd=1), _ev(minutes_ago=60, usd=2)])

        borrados = await liq.purge_old(db_session, now=NOW)
        rows = await liq.get_liquidations(db_session, "24h", "symbol", now=NOW)

        assert borrados == 1
        assert rows.data[0].total_usd == 2.0


class TestEndpoint:
    @pytest.fixture
    def client(self):
        with TestClient(app) as client:
            yield client

    def test_sin_auth_devuelve_401(self, client):
        assert client.get("/api/v1/liquidaciones").status_code == 401

    def test_openapi_limita_la_ventana(self, client):
        spec = client.get("/openapi.json").json()
        params = spec["paths"]["/api/v1/liquidaciones"]["get"]["parameters"]
        window = next(p for p in params if p["name"] == "window")
        assert window["schema"]["enum"] == ["5m", "15m", "1h", "4h", "24h"]

    async def test_handler_devuelve_envoltorio_con_meta(self, db_session):
        from src.routers import liquidations as router

        # El handler usa la hora real, asi que el evento va con la hora real (no con NOW fija).
        ahora = liq.LiqEvent(ts=datetime.now(timezone.utc), exchange="binance", symbol="BTC", side="long", notional_usd=70.0)
        await liq.record_events(db_session, [ahora])

        resp = await router.get_liquidations(window="1h", by="symbol", db=db_session, api_key="k")

        assert resp.ok is True
        assert resp.data[0].key == "BTC"
        assert resp.meta.window == "1h"
        assert resp.meta.coverage_from is not None
