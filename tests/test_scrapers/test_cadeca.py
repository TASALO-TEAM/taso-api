"""Tests for CADECA web scraper."""

import pytest
from httpx import Request, Response

from src.scrapers.cadeca import fetch_cadeca


@pytest.mark.asyncio
async def test_fetch_cadeca_success(cadeca_sample_html, monkeypatch):
    """fetch_cadeca extrae tasas correctamente del HTML."""
    
    mock_response = Response(
        status_code=200,
        text=cadeca_sample_html,
        request=Request("GET", "https://www.cadeca.cu")
    )
    
    async def mock_get(*args, **kwargs):
        return mock_response
    
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    
    result = await fetch_cadeca()
    
    assert result is not None
    assert "USD" in result
    assert result["USD"]["compra"] == 120.00
    assert result["USD"]["venta"] == 125.00
    assert "EUR" in result
    assert result["EUR"]["compra"] == 130.00
    assert result["EUR"]["venta"] == 135.00


@pytest.mark.asyncio
async def test_fetch_cadeca_empty_table(monkeypatch):
    """fetch_cadeca maneja tabla vacía."""
    
    empty_html = "<html><body><table></table></body></html>"
    
    mock_response = Response(
        status_code=200,
        text=empty_html,
        request=Request("GET", "https://www.cadeca.cu")
    )
    
    async def mock_get(*args, **kwargs):
        return mock_response
    
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    
    result = await fetch_cadeca()
    
    assert result == {}


@pytest.mark.asyncio
async def test_fetch_cadeca_timeout(monkeypatch):
    """fetch_cadeca maneja timeout."""
    import httpx
    
    async def mock_get(*args, **kwargs):
        raise httpx.ReadTimeout("Request timed out")
    
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    
    result = await fetch_cadeca()
    
    assert result is None


@pytest.mark.asyncio
async def test_fetch_cadeca_http_error(monkeypatch):
    """fetch_cadeca maneja error HTTP 404/500."""
    import httpx
    
    async def mock_get(*args, **kwargs):
        raise httpx.HTTPStatusError(
            "Not Found",
            request=Request("GET", "https://www.cadeca.cu"),
            response=Response(status_code=404, request=Request("GET", "https://www.cadeca.cu"))
        )
    
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    
    result = await fetch_cadeca()
    
    assert result is None
