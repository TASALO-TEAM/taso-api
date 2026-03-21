"""Tests for ElToque API scraper."""

import pytest
from unittest.mock import AsyncMock, patch
from httpx import Request, Response

from src.scrapers.eltoque import fetch_eltoque


@pytest.mark.asyncio
async def test_fetch_eltoque_success(eltoque_sample_data, monkeypatch):
    """fetch_eltoque obtiene datos correctamente de la API."""
    
    mock_response = Response(
        status_code=200,
        json=eltoque_sample_data,
        request=Request("GET", "https://tasas.eltoque.com/v1/trmi")
    )
    
    async def mock_get(*args, **kwargs):
        return mock_response
    
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    
    result = await fetch_eltoque(
        api_key="test_key",
        api_url="https://tasas.eltoque.com/v1/trmi"
    )
    
    assert result is not None
    assert result["fecha"] == "2026-03-21"
    assert result["hora"] == 14
    assert "USD" in result["tasas"]
    assert result["tasas"]["USD"] == 365.00


@pytest.mark.asyncio
async def test_fetch_eltoque_invalid_api_key(monkeypatch):
    """fetch_eltoque maneja API key inválida (401)."""
    
    mock_response = Response(
        status_code=401,
        text="Unauthorized",
        request=Request("GET", "https://tasas.eltoque.com/v1/trmi")
    )
    
    async def mock_get(*args, **kwargs):
        return mock_response
    
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    
    result = await fetch_eltoque(
        api_key="invalid_key",
        api_url="https://tasas.eltoque.com/v1/trmi"
    )
    
    assert result is None


@pytest.mark.asyncio
async def test_fetch_eltoque_timeout(monkeypatch):
    """fetch_eltoque maneja timeout de la API."""
    import httpx
    
    async def mock_get(*args, **kwargs):
        raise httpx.ReadTimeout("Request timed out")
    
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    
    result = await fetch_eltoque(
        api_key="test_key",
        api_url="https://tasas.eltoque.com/v1/trmi"
    )
    
    assert result is None


@pytest.mark.asyncio
async def test_fetch_eltoque_missing_api_key():
    """fetch_eltoque retorna None si no hay API key."""
    result = await fetch_eltoque(api_key="", api_url="https://example.com")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_eltoque_malformed_json(monkeypatch):
    """fetch_eltoque maneja JSON malformado."""
    import json
    
    mock_response = Response(
        status_code=200,
        text="not valid json{{{",
        request=Request("GET", "https://example.com")
    )
    
    async def mock_get(*args, **kwargs):
        return mock_response
    
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    
    result = await fetch_eltoque(
        api_key="test_key",
        api_url="https://example.com"
    )
    
    assert result is None
