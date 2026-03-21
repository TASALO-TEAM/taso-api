"""Tests for BCC web scraper."""

import pytest
from httpx import Request, Response

from src.scrapers.bcc import fetch_bcc


@pytest.fixture
def bcc_sample_html() -> str:
    """HTML de ejemplo de BCC para tests."""
    return """
    <html>
    <body>
        <table class="tabla-tablas">
            <tbody>
                <tr>
                    <td>USD</td>
                    <td class="text-right">24.00</td>
                </tr>
                <tr>
                    <td>EUR</td>
                    <td class="text-right">26.50</td>
                </tr>
                <tr>
                    <td>MLC</td>
                    <td class="text-right">10.00</td>
                </tr>
            </tbody>
        </table>
    </body>
    </html>
    """


@pytest.mark.asyncio
async def test_fetch_bcc_success(bcc_sample_html, monkeypatch):
    """fetch_bcc extrae tasas oficiales correctamente."""
    
    mock_response = Response(
        status_code=200,
        text=bcc_sample_html,
        request=Request("GET", "https://www.bc.gob.cu")
    )
    
    async def mock_get(*args, **kwargs):
        return mock_response
    
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    
    result = await fetch_bcc()
    
    assert result is not None
    assert "USD" in result
    assert result["USD"] == 24.00
    assert "EUR" in result
    assert result["EUR"] == 26.50
    assert "MLC" in result
    assert result["MLC"] == 10.00


@pytest.mark.asyncio
async def test_fetch_bcc_empty_table(monkeypatch):
    """fetch_bcc maneja tabla vacía."""
    
    empty_html = "<html><body><table></table></body></html>"
    
    mock_response = Response(
        status_code=200,
        text=empty_html,
        request=Request("GET", "https://www.bc.gob.cu")
    )
    
    async def mock_get(*args, **kwargs):
        return mock_response
    
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    
    result = await fetch_bcc()
    
    assert result == {}


@pytest.mark.asyncio
async def test_fetch_bcc_timeout(monkeypatch):
    """fetch_bcc maneja timeout."""
    import httpx
    
    async def mock_get(*args, **kwargs):
        raise httpx.ReadTimeout("Request timed out")
    
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    
    result = await fetch_bcc()
    
    assert result is None


@pytest.mark.asyncio
async def test_fetch_bcc_http_error(monkeypatch):
    """fetch_bcc maneja error HTTP."""
    import httpx
    
    async def mock_get(*args, **kwargs):
        raise httpx.HTTPStatusError(
            "Service Unavailable",
            request=Request("GET", "https://www.bc.gob.cu"),
            response=Response(status_code=503, request=Request("GET", "https://www.bc.gob.cu"))
        )
    
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    
    result = await fetch_bcc()
    
    assert result is None
