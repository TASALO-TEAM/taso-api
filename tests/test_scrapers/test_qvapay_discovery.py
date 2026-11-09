"""Tests del descubrimiento automático de monedas de QvaPay (coins/v2 + sondeo por ciclos)."""

import time

import httpx
import pytest
from httpx import Request, Response

from src.scrapers import qvapay as qv
from src.scrapers.qvapay import QVAPAY_COINS, QVAPAY_COINS_URL, QVAPAY_URL, fetch_qvapay, qvapay_meta
from src.schemas.rates import QvaPayRate


@pytest.fixture(autouse=True)
def _estado_limpio(monkeypatch):
    """Lo descubierto vive en el módulo: se vacía antes y después para no contaminar otras pruebas."""
    qv.reset_state()
    monkeypatch.setattr(qv, "PROBE_GAP", 0)
    yield
    qv.reset_state()


def _ok(payload, url=QVAPAY_URL) -> Response:
    return Response(status_code=200, json=payload, request=Request("GET", url))


def _coin(tick, name, category, p2p=True):
    return {"tick": tick, "name": name, "coins_categories_id": category, "enabled_p2p": p2p}


CATALOGO = [
    _coin("BANK_CUP", "CUP", 2),
    _coin("CUPCASH", "CUP Cash", 3),
    _coin("USDCASH", "USD Cash", 3),
    _coin("PIX", "Pix", 2),
    _coin("PAYPAL", "PayPal", 4),
    _coin("BANK", "USD", 2),  # 1 USD por USD: no aporta tasa
    _coin("BANK_INTL", "USD Internacional (SWIFT)", 2),
    _coin("BTC", "Bitcoin", 1),  # criptomoneda: no es método de pago
    _coin("AIRBNB", "AirBnB", 2, p2p=False),  # sin P2P activo
]


def _instalar(monkeypatch, datos, catalogo=CATALOGO):
    """datos: {código: payload | excepción | Response}. Devuelve la lista de monedas pedidas, en orden."""
    pedidas: list[str] = []

    async def mock_get(self, url, **kwargs):
        if url == QVAPAY_COINS_URL:
            if isinstance(catalogo, Exception):
                raise catalogo
            return _ok(catalogo, QVAPAY_COINS_URL)
        coin = kwargs["params"]["coin"]
        pedidas.append(coin)
        valor = datos.get(coin, {"average_buy": None, "average_sell": None, "count": 0})
        if isinstance(valor, Exception):
            raise valor
        if isinstance(valor, Response):
            return valor
        return _ok(valor)

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    return pedidas


CON_DATOS = {"average_buy": 1.0, "average_sell": 1.1, "count": 12}


@pytest.mark.asyncio
async def test_descubre_una_moneda_nueva_y_la_incluye_al_siguiente_ciclo(monkeypatch):
    _instalar(monkeypatch, {"USDCASH": CON_DATOS, "BANK_CUP": CON_DATOS})

    primero = await fetch_qvapay()
    assert "USDCASH" not in primero  # se descubre en este ciclo, se consulta desde el siguiente

    segundo = await fetch_qvapay()
    assert segundo["USDCASH"] == {"buy": 1.0, "sell": 1.1}
    # Las monedas fijas siguen con su etiqueta de siempre.
    assert "CUP" in segundo


@pytest.mark.asyncio
async def test_meta_trae_nombre_tipo_y_operaciones(monkeypatch):
    _instalar(monkeypatch, {"USDCASH": CON_DATOS, "BANK_CUP": {"average_buy": 1100, "average_sell": 1110, "count": 1031}})

    await fetch_qvapay()
    await fetch_qvapay()

    assert qvapay_meta("USDCASH") == {"name": "USD Cash", "kind": "cash", "count": 12}
    # Una fija se describe por su etiqueta pública (CUP -> BANK_CUP).
    assert qvapay_meta("CUP") == {"name": "CUP", "kind": "bank", "count": 1031}
    # Una moneda que no se conoce no inventa datos.
    assert qvapay_meta("NOEXISTE") == {}
    # Y encaja en el esquema de la API.
    assert QvaPayRate(rate=1.05, change="neutral", **qvapay_meta("USDCASH")).kind == "cash"


@pytest.mark.asyncio
async def test_no_sondea_cripto_ni_bank_ni_las_sin_p2p_ni_las_fijas(monkeypatch):
    pedidas = _instalar(monkeypatch, {})
    monkeypatch.setattr(qv, "PROBE_PER_CYCLE", 20)

    await fetch_qvapay()

    sondeadas = set(pedidas) - set(QVAPAY_COINS.values())
    assert sondeadas == {"USDCASH", "PIX", "PAYPAL"}


@pytest.mark.asyncio
async def test_sondea_de_a_pocas_por_ciclo_y_recorre_todas(monkeypatch):
    pedidas = _instalar(monkeypatch, {})
    monkeypatch.setattr(qv, "PROBE_PER_CYCLE", 2)

    ciclos = []
    for _ in range(3):
        pedidas.clear()
        await fetch_qvapay()
        ciclos.append(set(pedidas) - set(QVAPAY_COINS.values()))

    assert all(len(c) == 2 for c in ciclos)
    assert set().union(*ciclos) == {"USDCASH", "PIX", "PAYPAL"}


@pytest.mark.asyncio
async def test_un_429_al_sondear_no_la_marca_como_activa(monkeypatch):
    limite = Response(status_code=429, request=Request("GET", QVAPAY_URL))
    _instalar(monkeypatch, {"USDCASH": limite, "PIX": CON_DATOS})
    monkeypatch.setattr(qv, "PROBE_PER_CYCLE", 20)

    await fetch_qvapay()
    segundo = await fetch_qvapay()

    assert "PIX" in segundo
    assert "USDCASH" not in segundo


@pytest.mark.asyncio
async def test_si_coins_v2_falla_las_fijas_siguen_funcionando(monkeypatch):
    _instalar(monkeypatch, {"BANK_CUP": CON_DATOS}, catalogo=httpx.ConnectError("sin red"))

    resultado = await fetch_qvapay()

    assert resultado == {"CUP": {"buy": 1.0, "sell": 1.1}}
    assert qvapay_meta("CUP") == {"count": 12}  # sin catálogo no hay nombre ni tipo, pero no se rompe


@pytest.mark.asyncio
async def test_coins_v2_se_lee_una_vez_por_ventana(monkeypatch):
    lecturas = []

    async def mock_get(self, url, **kwargs):
        if url == QVAPAY_COINS_URL:
            lecturas.append(url)
            return _ok(CATALOGO, QVAPAY_COINS_URL)
        return _ok(CON_DATOS)

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)

    await fetch_qvapay()
    await fetch_qvapay()
    await fetch_qvapay()

    assert len(lecturas) == 1


@pytest.mark.asyncio
async def test_una_descubierta_sin_datos_por_7_dias_vuelve_a_candidata(monkeypatch):
    _instalar(monkeypatch, {"USDCASH": CON_DATOS})
    monkeypatch.setattr(qv, "PROBE_PER_CYCLE", 0)  # sin sondeos: solo se prueba el vencimiento
    qv._extras["USDCASH"] = time.time() - qv.EXTRA_TTL - 60
    qv._counts["USDCASH"] = 12
    # Con datos se renueva y no vence.
    await fetch_qvapay()
    assert "USDCASH" in qv._extras

    # Sin datos y pasado el plazo se suelta.
    _instalar(monkeypatch, {})
    qv._extras["USDCASH"] = time.time() - qv.EXTRA_TTL - 60
    await fetch_qvapay()
    assert "USDCASH" not in qv._extras
    assert "USDCASH" not in qv._counts


def test_nombres_se_limpian():
    assert qv._clean_name("  CUP\x00 \n Cash  ", "X") == "CUP Cash"
    assert qv._clean_name("", "TICK") == "TICK"
    assert qv._clean_name(None, "TICK") == "TICK"
    assert len(qv._clean_name("A" * 200, "X")) == 40
