"""Tests del modo híbrido de ElToque: API oficial + Cubanomic + avisos de estado."""

import base64
import json
import time
from types import SimpleNamespace

import httpx
import pytest

from src.scrapers import cubanomic_live, eltoque
from src.scrapers.eltoque import ElToqueError
from src.services import eltoque_health, rates_service
from src.services.rates_service import merge_eltoque_sources

API = {"tasas": {"USD": 930, "ECU": 1000, "MLC": 850, "USDT_TRC20": 1100}, "date": "2026-11-17"}
CUB = {
    "tasas": {"USD": 925.0, "EUR": 998.0, "USDT": 1090.0, "CAD": 600.0, "BNB": 450.0},
    "meta": {"CAD": {"messages": 6}, "BNB": {"messages": 0}},
    "source": "cubanomic_live",
}


# ---------- mezcla ----------

def test_merge_api_manda_y_cubanomic_completa():
    m = merge_eltoque_sources(API, CUB)
    assert m["mode"] == "hybrid"
    assert m["tasas"]["USD"] == 930.0          # la API gana en las monedas comunes
    assert m["tasas"]["CAD"] == 600.0          # lo que falta viene de Cubanomic
    assert m["origin"]["USD"] == "api"
    assert m["origin"]["CAD"] == "cubanomic"
    assert m["meta"]["BNB"]["messages"] == 0


def test_merge_no_duplica_monedas_con_alias():
    m = merge_eltoque_sources(API, CUB)
    # ECU (API) y EUR (Cubanomic) son la misma moneda: una sola entrada, de la API
    assert "ECU" not in m["tasas"]
    assert m["tasas"]["EUR"] == 1000.0 and m["origin"]["EUR"] == "api"
    assert m["tasas"]["USDT"] == 1100.0 and m["origin"]["USDT"] == "api"


def test_merge_solo_api_si_cubanomic_no_agrega_nada():
    m = merge_eltoque_sources(API, {"tasas": {"USD": 1.0}, "meta": {}})
    assert m["mode"] == "api"


def test_merge_api_caida_todo_desde_cubanomic():
    m = merge_eltoque_sources(None, CUB)
    assert m["mode"] == "cubanomic"
    assert set(m["origin"].values()) == {"cubanomic"}


def test_merge_ambas_caidas():
    assert merge_eltoque_sources(None, None) is None


# ---------- reintentos ----------

@pytest.fixture(autouse=True)
def _sin_esperas(monkeypatch):
    monkeypatch.setattr(rates_service, "_RETRY_BACKOFF", 0)
    eltoque_health.reset_state()


async def test_token_vencido_no_se_reintenta(monkeypatch):
    llamadas = []

    async def fake(timeout=0):
        llamadas.append(1)
        raise ElToqueError("token inválido o vencido (HTTP 401)", retryable=False)

    monkeypatch.setattr(rates_service, "fetch_eltoque_strict", fake)
    data, reason = await rates_service._eltoque_api_with_retries()
    assert data is None and "vencido" in reason
    assert len(llamadas) == 1


async def test_reintenta_hasta_tener_exito(monkeypatch):
    llamadas = []

    async def fake(timeout=0):
        llamadas.append(1)
        if len(llamadas) < 3:
            raise ElToqueError("timeout")
        return API

    monkeypatch.setattr(rates_service, "fetch_eltoque_strict", fake)
    data, reason = await rates_service._eltoque_api_with_retries()
    assert data == API and reason is None
    assert len(llamadas) == 3


async def test_tres_fallos_devuelven_el_motivo(monkeypatch):
    async def fake(timeout=0):
        raise ElToqueError("timeout")

    monkeypatch.setattr(rates_service, "fetch_eltoque_strict", fake)
    data, reason = await rates_service._eltoque_api_with_retries()
    assert data is None and reason == "timeout"


def test_peor_caso_cabe_dentro_del_timeout_externo():
    # Regresión: 3 intentos de 8s + esperas (1s y 2s) = 27s debe ser < 40s, el timeout con el
    # que fetch_all_sources envuelve a ElToque; si no, el respaldo se cancela antes de usarse.
    assert 3 * 8.0 + (1.0 * 1 + 1.0 * 2) < 40


# ---------- flujo completo + avisos ----------

@pytest.fixture
def avisos(monkeypatch):
    enviados = []

    async def fake_notify(msg):
        enviados.append(msg)

    monkeypatch.setattr(eltoque_health, "notify", fake_notify)
    monkeypatch.setattr(
        eltoque_health, "get_settings", lambda: SimpleNamespace(eltoque_api_key="")
    )
    return enviados


async def _flujo(monkeypatch, api, cub, reason="timeout"):
    async def fake_api(*_a, **_k):
        return api, (None if api else reason)

    async def fake_cub(**_k):
        return cub

    monkeypatch.setattr(rates_service, "_eltoque_api_with_retries", fake_api)
    monkeypatch.setattr(rates_service, "fetch_cubanomic_live", fake_cub)
    return await rates_service._fetch_eltoque_merged()


async def test_api_caida_usa_cubanomic_y_avisa_una_vez(monkeypatch, avisos):
    r1 = await _flujo(monkeypatch, None, CUB, "token inválido o vencido (HTTP 401)")
    assert r1["mode"] == "cubanomic"
    assert len(avisos) == 1 and "vencido" in avisos[0] and "Cubanomic" in avisos[0]

    await _flujo(monkeypatch, None, CUB, "token inválido o vencido (HTTP 401)")
    assert len(avisos) == 1  # mismo estado: no se repite


async def test_recuperacion_avisa(monkeypatch, avisos):
    await _flujo(monkeypatch, None, CUB)
    await _flujo(monkeypatch, API, CUB)
    assert len(avisos) == 2 and "recuperada" in avisos[1]


async def test_todo_caido_avisa_y_devuelve_none(monkeypatch, avisos):
    assert await _flujo(monkeypatch, None, None) is None
    assert len(avisos) == 1 and "fallaron" in avisos[0]


async def test_arranque_en_ok_no_avisa(monkeypatch, avisos):
    await _flujo(monkeypatch, API, CUB)
    assert avisos == []


async def test_recordatorio_cada_6_horas(monkeypatch, avisos):
    reloj = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: reloj[0])
    await _flujo(monkeypatch, None, CUB)
    reloj[0] += eltoque_health.REMINDER_SECONDS - 1
    await _flujo(monkeypatch, None, CUB)
    assert len(avisos) == 1
    reloj[0] += 2
    await _flujo(monkeypatch, None, CUB)
    assert len(avisos) == 2


# ---------- vencimiento del token ----------

def _jwt(dias):
    exp = int(time.time() + dias * 86400 + 3600)
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    return f"x.{payload}.y"


def test_token_days_left():
    assert eltoque_health.token_days_left(_jwt(10)) == 10
    assert eltoque_health.token_days_left(_jwt(-2)) < 0
    assert eltoque_health.token_days_left("no-es-un-jwt") is None


async def test_aviso_de_vencimiento_una_vez_por_umbral(monkeypatch, avisos):
    monkeypatch.setattr(
        eltoque_health, "get_settings", lambda: SimpleNamespace(eltoque_api_key=_jwt(6))
    )
    await eltoque_health.report("ok", None)
    await eltoque_health.report("ok", None)
    assert len(avisos) == 1 and "6 día" in avisos[0]

    monkeypatch.setattr(
        eltoque_health, "get_settings", lambda: SimpleNamespace(eltoque_api_key=_jwt(2))
    )
    await eltoque_health.report("ok", None)  # cruza el umbral de 3 días
    assert len(avisos) == 2


async def test_token_lejano_no_avisa(monkeypatch, avisos):
    monkeypatch.setattr(
        eltoque_health, "get_settings", lambda: SimpleNamespace(eltoque_api_key=_jwt(200))
    )
    await eltoque_health.report("ok", None)
    assert avisos == []


# ---------- cliente HTTP de ElToque ----------

def _patch_http(monkeypatch, handler):
    real = httpx.AsyncClient
    monkeypatch.setattr(
        eltoque.httpx, "AsyncClient", lambda *a, **k: real(transport=httpx.MockTransport(handler))
    )


@pytest.mark.parametrize(
    "status,body,retryable",
    [
        (401, {"msg": "Token has expired"}, False),
        (200, {"msg": "Token has expired"}, False),
        (500, {}, True),
        (429, {}, True),
    ],
)
async def test_eltoque_clasifica_errores(monkeypatch, status, body, retryable):
    _patch_http(monkeypatch, lambda req: httpx.Response(status, json=body))
    with pytest.raises(ElToqueError) as exc:
        await eltoque.fetch_eltoque_strict(api_key="k", api_url="https://x.test/trmi")
    assert exc.value.retryable is retryable


async def test_eltoque_ok(monkeypatch):
    _patch_http(monkeypatch, lambda req: httpx.Response(200, json=API))
    data = await eltoque.fetch_eltoque_strict(api_key="k", api_url="https://x.test/trmi")
    assert data["tasas"]["USD"] == 930


async def test_eltoque_sin_clave_no_reintenta():
    with pytest.raises(ElToqueError) as exc:
        await eltoque.fetch_eltoque_strict(api_key="", api_url="https://x.test/trmi")
    assert exc.value.retryable is False


async def test_eltoque_tolerante_devuelve_none(monkeypatch):
    _patch_http(monkeypatch, lambda req: httpx.Response(401, json={"msg": "Token has expired"}))
    assert await eltoque.fetch_eltoque(api_key="k", api_url="https://x.test/trmi") is None


# ---------- normalizador de Cubanomic ----------

def _stat(median, messages):
    return {"median": median, "count_messages": messages, "median_diff": 1.0}


def test_cubanomic_normaliza():
    raw = {
        "date": "2026-11-17",
        "statistics": {
            "USD": _stat(930, 389),
            "ECU": _stat(1000, 61),
            "EUR": _stat(990, 2),          # alias: gana ECU (más ofertas)
            "USDT_TRC20": _stat(1092, 35),
            "CUP": _stat(716, 4),          # moneda base: se descarta
            "AUD": _stat(2000, 0),         # valor fijo: se conserva pero con messages=0
            "XXX": _stat(0, 5),            # tasa 0: se descarta
            "YYY": {"median": None},       # sin mediana: se descarta
        },
    }
    out = cubanomic_live._normalize_to_eltoque_format(raw)
    assert out["tasas"]["EUR"] == 1000.0
    assert out["tasas"]["USDT"] == 1092.0
    assert out["tasas"]["AUD"] == 2000.0 and out["meta"]["AUD"]["messages"] == 0
    for ausente in ("CUP", "ECU", "XXX", "YYY", "USDT_TRC20"):
        assert ausente not in out["tasas"]


def test_cubanomic_sin_datos_devuelve_none():
    assert cubanomic_live._normalize_to_eltoque_format({"statistics": {}}) is None
    assert cubanomic_live._normalize_to_eltoque_format({}) is None


def test_cubanomic_uds_es_zelle():
    # Cubanomic publica Zelle con el codigo UDS; el resto del sistema lo ve como ZELLE
    out = cubanomic_live._normalize_to_eltoque_format(
        {"statistics": {"UDS": _stat(915, 12), "USD": _stat(930, 389)}}
    )
    assert out["tasas"]["ZELLE"] == 915 and "UDS" not in out["tasas"]
    assert out["meta"]["ZELLE"]["messages"] == 12
