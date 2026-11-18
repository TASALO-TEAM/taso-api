"""Catalogo de monedas de ElToque: grupo, orden, tier y offers (agrupado para clientes)."""

from src.schemas.rates import ElToqueRate
from src.services.eltoque_catalog import eltoque_meta, eltoque_sort_key
from src.services.rates_service import _normalize_eltoque_data


def test_principales_en_orden_zelle_tras_usd():
    codes = ["CLA", "MLC", "ZELLE", "USD", "EUR"]
    assert sorted(codes, key=eltoque_sort_key) == ["EUR", "USD", "ZELLE", "MLC", "CLA"]


def test_grupos_main_crypto_other_en_ese_orden():
    codes = ["CAD", "BTC", "USD"]
    assert sorted(codes, key=eltoque_sort_key) == ["USD", "BTC", "CAD"]
    assert eltoque_meta("USD", None)["group"] == "main"
    assert eltoque_meta("BTC", None)["group"] == "crypto"
    assert eltoque_meta("USDT_ERC20", None)["group"] == "crypto"
    assert eltoque_meta("CAD", None)["group"] == "other"


def test_otras_conocidas_primero_y_resto_alfabetico():
    codes = ["ZZZ", "JMD", "GBP", "CAD", "AAA", "MXN"]
    assert sorted(codes, key=eltoque_sort_key) == ["CAD", "MXN", "GBP", "AAA", "JMD", "ZZZ"]


def test_tier_reference_solo_con_cero_ofertas():
    assert eltoque_meta("BNB", 0)["tier"] == "reference"
    assert eltoque_meta("BNB", 1)["tier"] == "market"
    assert eltoque_meta("USD", None)["tier"] == "market"  # viene de la API oficial


def test_moneda_desconocida_no_rompe():
    meta = eltoque_meta("XYZ", 2)
    assert meta["name"] is None
    assert meta["group"] == "other"
    assert meta["offers"] == 2


def test_normalize_guarda_offers_solo_de_monedas_de_cubanomic():
    data = {
        "tasas": {"USD": 930, "CAD": 600, "BNB": 450},
        "origin": {"USD": "api", "CAD": "cubanomic", "BNB": "cubanomic"},
        "meta": {"USD": {"messages": 389}, "CAD": {"messages": 6}, "BNB": {"messages": 0}},
    }
    offers = {r["currency"]: r["offers"] for r in _normalize_eltoque_data(data)}
    assert offers == {"USD": None, "CAD": 6, "BNB": 0}


def test_normalize_sin_origin_ni_meta_deja_offers_en_none():
    rows = _normalize_eltoque_data({"tasas": {"USD": 930, "EUR": 1000}})
    assert [r["offers"] for r in rows] == [None, None]


def test_schema_acepta_meta_del_catalogo():
    rate = ElToqueRate(rate=915.0, change="neutral", **eltoque_meta("ZELLE", 3))
    assert (rate.name, rate.group, rate.tier, rate.offers) == ("Zelle", "main", "market", 3)


def test_build_eltoque_rates_ordena_por_grupo_y_marca_tier():
    from src.services.eltoque_catalog import build_eltoque_rates

    rates = {
        "BNB": {"rate": 450.0, "offers": 0},
        "CAD": {"rate": 600.0, "change": "up", "prev_rate": 590.0, "offers": 6},
        "ZELLE": {"rate": 915.0, "offers": 3},
        "USD": {"rate": 930.0, "offers": None},
        "EUR": {"rate": 1000.0},
    }
    out = build_eltoque_rates(rates)
    assert list(out) == ["EUR", "USD", "ZELLE", "BNB", "CAD"]
    assert (out["BNB"].tier, out["BNB"].group) == ("reference", "crypto")
    assert (out["USD"].tier, out["USD"].offers) == ("market", None)
    assert (out["CAD"].change, out["CAD"].prev_rate) == ("up", 590.0)


def test_save_snapshot_guarda_offers():
    import asyncio
    from unittest.mock import MagicMock

    from src.services.rates_service import save_snapshot

    session = MagicMock()
    data = {
        "tasas": {"USD": 930, "CAD": 600},
        "origin": {"USD": "api", "CAD": "cubanomic"},
        "meta": {"CAD": {"messages": 6}},
    }
    asyncio.run(save_snapshot(session, "eltoque", data))
    snaps = session.add_all.call_args[0][0]
    assert {s.currency: s.offers for s in snaps} == {"USD": None, "CAD": 6}
