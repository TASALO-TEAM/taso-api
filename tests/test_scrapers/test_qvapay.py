"""Tests for QvaPay P2P scraper."""

import httpx
import pytest
from httpx import Request, Response

from src.scrapers.qvapay import QVAPAY_COINS, QVAPAY_URL, fetch_qvapay


def _ok(payload) -> Response:
    return Response(status_code=200, json=payload, request=Request("GET", QVAPAY_URL))


def _patch_get(monkeypatch, handler):
    async def mock_get(self, url, **kwargs):
        return handler(kwargs["params"]["coin"])

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)


@pytest.mark.asyncio
async def test_fetch_qvapay_success(monkeypatch):
    """Devuelve compra/venta por etiqueta pública."""

    def handler(coin):
        if coin == "BANK_CUP":
            return _ok({"average_buy": 978.31, "average_sell": 984.78})
        return _ok({"average_buy": 1.02, "average_sell": 1.05})

    _patch_get(monkeypatch, handler)

    result = await fetch_qvapay()

    assert result is not None
    assert set(result) == set(QVAPAY_COINS)
    assert result["CUP"] == {"buy": 978.31, "sell": 984.78}
    assert result["ZELLE"] == {"buy": 1.02, "sell": 1.05}


@pytest.mark.asyncio
async def test_fetch_qvapay_one_side_null(monkeypatch):
    """Si falta un lado queda en None, el otro se conserva."""
    _patch_get(monkeypatch, lambda coin: _ok({"average_buy": 1.45, "average_sell": None}))

    result = await fetch_qvapay()

    assert result["MLC"] == {"buy": 1.45, "sell": None}


@pytest.mark.asyncio
async def test_fetch_qvapay_coin_without_data_is_omitted(monkeypatch):
    """Una moneda con ambos lados nulos (SBERBANK) no aparece."""

    def handler(coin):
        if coin == "SBERBANK":
            return _ok({"average_buy": None, "average_sell": None})
        return _ok({"average_buy": 1.0, "average_sell": 1.1})

    _patch_get(monkeypatch, handler)

    result = await fetch_qvapay()

    assert "SBERBANK" not in result
    assert "CUP" in result


@pytest.mark.asyncio
async def test_fetch_qvapay_partial_failure(monkeypatch):
    """Un error de red o HTTP en una moneda no tumba las demás."""

    def handler(coin):
        if coin == "ZELLE":
            raise httpx.ConnectError("sin red")
        if coin == "ETECSA":
            return Response(status_code=500, request=Request("GET", QVAPAY_URL))
        return _ok({"average_buy": 2.0, "average_sell": 2.2})

    _patch_get(monkeypatch, handler)

    result = await fetch_qvapay()

    assert result is not None
    assert "ZELLE" not in result
    assert "ETECSA" not in result
    assert result["CUP"] == {"buy": 2.0, "sell": 2.2}


@pytest.mark.asyncio
async def test_fetch_qvapay_all_down_returns_none(monkeypatch):
    """Si no responde ninguna moneda devuelve None."""

    def handler(coin):
        raise httpx.ReadTimeout("timeout")

    _patch_get(monkeypatch, handler)

    assert await fetch_qvapay() is None
