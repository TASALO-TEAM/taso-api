"""Tests for Binance API scraper."""

import pytest
from httpx import Request, Response

from src.scrapers.binance import fetch_binance


@pytest.mark.asyncio
async def test_fetch_binance_success(binance_sample_data, monkeypatch):
    """fetch_binance obtiene precios correctamente."""

    mock_response = Response(
        status_code=200,
        json=binance_sample_data,
        request=Request("GET", "https://api.binance.us/api/v3/ticker/price")
    )

    async def mock_get(*args, **kwargs):
        return mock_response

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)

    result = await fetch_binance()

    assert result is not None
    assert "BTCUSDT" in result
    assert result["BTCUSDT"] == 67500.00
    assert "ETHUSDT" in result


@pytest.mark.asyncio
async def test_fetch_binance_custom_symbols(monkeypatch):
    """fetch_binance funciona con símbolos personalizados."""
    
    custom_data = [
        {"symbol": "BTCUSDT", "price": "70000.00"},
        {"symbol": "BNBUSDT", "price": "450.00"}
    ]
    
    mock_response = Response(
        status_code=200,
        json=custom_data,
        request=Request("GET", "https://api.binance.com/api/v3/ticker/price")
    )
    
    async def mock_get(*args, **kwargs):
        return mock_response
    
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    
    result = await fetch_binance(symbols=["BTCUSDT", "BNBUSDT"])
    
    assert result is not None
    assert "BTCUSDT" in result
    assert "BNBUSDT" in result


@pytest.mark.asyncio
async def test_fetch_binance_timeout(monkeypatch):
    """fetch_binance maneja timeout."""
    import httpx
    
    async def mock_get(*args, **kwargs):
        raise httpx.ReadTimeout("Request timed out")
    
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    
    result = await fetch_binance()
    
    assert result is None


@pytest.mark.asyncio
async def test_fetch_binance_empty_response(monkeypatch):
    """fetch_binance maneja respuesta vacía."""
    
    mock_response = Response(
        status_code=200,
        json=[],
        request=Request("GET", "https://api.binance.com/api/v3/ticker/price")
    )
    
    async def mock_get(*args, **kwargs):
        return mock_response
    
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    
    result = await fetch_binance()
    
    assert result == {}
