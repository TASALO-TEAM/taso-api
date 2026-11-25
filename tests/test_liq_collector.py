"""Tests del colector de liquidaciones (taso-bot M3b): parsers, filtro, dedupe y volcado.

Los formatos salen de muestras reales medidas desde el VPS el 2026-11-25.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from src.services import liq_collector as lc
from src.services import liquidations as liq

NOW = datetime(2026, 11, 25, 18, 0, 30, tzinfo=timezone.utc)


def ms(dt):
    return int(dt.timestamp() * 1000)


def _bn(sym="BTCUSDT", side="SELL", z="0.5", ap="60000", t=NOW):
    return json.dumps({"e": "forceOrder", "E": ms(t), "o": {"s": sym, "S": side, "q": z, "z": z, "ap": ap, "T": ms(t)}})


def _by(sym="BTCUSDT", side="Buy", v="0.1", p="60000", t=NOW):
    return json.dumps({"topic": f"allLiquidation.{sym}", "type": "snapshot", "ts": ms(t),
                       "data": [{"T": ms(t), "s": sym, "S": side, "v": v, "p": p}]})


def _ok(inst="ETH-USDT-SWAP", pos="long", sz="10", px="2000", t=NOW):
    return json.dumps({"arg": {"channel": "liquidation-orders", "instType": "SWAP"},
                       "data": [{"instId": inst, "instType": "SWAP",
                                 "details": [{"posSide": pos, "sz": sz, "bkPx": px, "ts": str(ms(t))}]}]})


class TestBinance:
    def test_sell_es_un_long_liquidado_y_notional_es_cantidad_por_precio(self):
        ev = lc.parse_binance(_bn(), NOW)
        assert (ev.exchange, ev.symbol, ev.side, ev.notional_usd) == ("binance", "BTC", "long", 30000.0)

    def test_buy_es_un_short_liquidado(self):
        assert lc.parse_binance(_bn(side="BUY"), NOW).side == "short"

    def test_quita_usdc_y_conserva_el_prefijo_1000(self):
        assert lc.parse_binance(_bn(sym="1000BONKUSDC"), NOW).symbol == "1000BONK"

    def test_ignora_contratos_coin_margined_por_ambiguedad_de_tamano(self):
        assert lc.parse_binance(_bn(sym="BTCUSD_PERP"), NOW) is None

    def test_ignora_mensajes_ajenos_o_rotos(self):
        assert lc.parse_binance(json.dumps({"result": None, "id": 1}), NOW) is None
        assert lc.parse_binance("no es json", NOW) is None

    def test_descarta_eventos_viejos(self):
        viejo = NOW - timedelta(seconds=lc.MAX_AGE_SECONDS + 5)
        assert lc.parse_binance(_bn(t=viejo), NOW) is None


class TestBybit:
    def test_buy_es_un_long_liquidado_segun_la_documentacion_de_bybit(self):
        evs = lc.parse_bybit(_by(), NOW)
        assert [(e.exchange, e.symbol, e.side, e.notional_usd) for e in evs] == [("bybit", "BTC", "long", 6000.0)]

    def test_sell_es_un_short_liquidado(self):
        assert lc.parse_bybit(_by(side="Sell"), NOW)[0].side == "short"

    def test_acuses_y_otros_topics_no_generan_eventos(self):
        assert lc.parse_bybit(json.dumps({"success": True, "op": "subscribe"}), NOW) == []
        assert lc.parse_bybit(json.dumps({"topic": "tickers.BTCUSDT", "data": {}}), NOW) == []

    def test_descarta_eventos_viejos(self):
        assert lc.parse_bybit(_by(t=NOW - timedelta(minutes=10)), NOW) == []


class TestOkx:
    CT = {"ETH-USDT-SWAP": 0.1}

    def test_convierte_contratos_a_usd(self):
        evs = lc.parse_okx(_ok(), self.CT, NOW)
        assert [(e.exchange, e.symbol, e.side, e.notional_usd) for e in evs] == [("okx", "ETH", "long", 2000.0)]

    def test_instrumento_sin_valor_de_contrato_se_ignora(self):
        assert lc.parse_okx(_ok(inst="BTC-USD-SWAP"), self.CT, NOW) == []

    def test_avisos_y_acuses_no_generan_eventos(self):
        assert lc.parse_okx(json.dumps({"event": "notice", "code": "64010"}), self.CT, NOW) == []

    def test_descarta_el_snapshot_viejo_del_primer_mensaje(self):
        assert lc.parse_okx(_ok(t=NOW - timedelta(hours=3)), self.CT, NOW) == []

    def test_el_short_liquidado_llega_como_posside_short(self):
        assert lc.parse_okx(_ok(pos="short"), self.CT, NOW)[0].side == "short"


class _Ctx:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *a):
        return False


class TestCollector:
    async def test_deduplica_y_vuelca_en_lote(self, db_session):
        c = lc.LiqCollector(lambda: _Ctx(db_session))
        ev = lc.parse_binance(_bn(), NOW)
        c.ingest([ev, ev])

        assert await c.flush() == 1
        assert await c.flush() == 0  # buffer vacio: no toca la BD

        res = await liq.get_liquidations(db_session, "5m", "exchange", now=NOW)
        assert [(r.key, r.long_usd) for r in res.data] == [("binance", 30000.0)]

    async def test_un_fallo_de_bd_no_pierde_el_lote(self, db_session):
        class Roto:
            async def __aenter__(self):
                raise RuntimeError("bd caida")

            async def __aexit__(self, *a):
                return False

        c = lc.LiqCollector(lambda: Roto())
        c.ingest([lc.parse_binance(_bn(), NOW)])

        assert await c.flush() == 0
        assert len(c._buffer) == 1  # se reintenta en el siguiente volcado

    def test_espera_entre_reconexiones_crece_y_se_acota(self):
        assert [lc.next_delay(n) for n in (0, 1, 2, 3, 10)] == [1, 2, 4, 8, 60]
