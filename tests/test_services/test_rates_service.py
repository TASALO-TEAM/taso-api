"""Tests for rates_service.py."""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_fetch_all_sources_returns_all_four_sources():
    """fetch_all_sources ejecuta los 4 scrapers en paralelo."""
    from src.services.rates_service import fetch_all_sources
    
    with patch('src.services.rates_service.fetch_eltoque') as mock_eltoque, \
         patch('src.services.rates_service.fetch_binance') as mock_binance, \
         patch('src.services.rates_service.fetch_cadeca') as mock_cadeca, \
         patch('src.services.rates_service.fetch_bcc') as mock_bcc:
        
        # Setup mocks
        mock_eltoque.return_value = {'tasas': {'USD': 365.0}}
        mock_binance.return_value = {'BTCUSDT': '45000.00'}
        mock_cadeca.return_value = {'USD': {'compra': 120.0, 'venta': 125.0}}
        mock_bcc.return_value = {'USD': 125.0}
        
        result = await fetch_all_sources()
        
        assert result['eltoque'] == {'tasas': {'USD': 365.0}}
        assert result['binance'] == {'BTCUSDT': '45000.00'}
        assert result['cadeca'] == {'USD': {'compra': 120.0, 'venta': 125.0}}
        assert result['bcc'] == {'USD': 125.0}


@pytest.mark.asyncio
async def test_fetch_all_sources_handles_individual_failures():
    """Si un scraper falla, los demás continúan."""
    from src.services.rates_service import fetch_all_sources
    
    with patch('src.services.rates_service.fetch_eltoque') as mock_eltoque, \
         patch('src.services.rates_service.fetch_binance') as mock_binance, \
         patch('src.services.rates_service.fetch_cadeca') as mock_cadeca, \
         patch('src.services.rates_service.fetch_bcc') as mock_bcc:
        
        # ElToque falla, los demás ok
        mock_eltoque.side_effect = Exception("API timeout")
        mock_binance.return_value = {'BTCUSDT': '45000.00'}
        mock_cadeca.return_value = {'USD': {'compra': 120.0, 'venta': 125.0}}
        mock_bcc.return_value = {'USD': 125.0}
        
        result = await fetch_all_sources()
        
        assert result['eltoque'] is None  # Falló
        assert result['binance'] is not None
        assert result['cadeca'] is not None
        assert result['bcc'] is not None
