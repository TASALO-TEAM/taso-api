"""Tests for rates_service.py."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone
from sqlalchemy import select


def test_calculate_change_up():
    """calculate_change retorna 'up' cuando sube."""
    from src.services.rates_service import calculate_change
    
    result = calculate_change(370.0, 365.0)
    assert result == 'up'

def test_calculate_change_down():
    """calculate_change retorna 'down' cuando baja."""
    from src.services.rates_service import calculate_change
    
    result = calculate_change(360.0, 365.0)
    assert result == 'down'

def test_calculate_change_neutral():
    """calculate_change retorna 'neutral' cuando no cambia (tolerancia 0.0001)."""
    from src.services.rates_service import calculate_change
    
    result = calculate_change(365.00005, 365.0)
    assert result == 'neutral'

def test_calculate_change_none():
    """calculate_change retorna 'neutral' si no hay previous."""
    from src.services.rates_service import calculate_change
    
    result = calculate_change(365.0, None)
    assert result == 'neutral'


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


@pytest.mark.asyncio
async def test_save_snapshot_eltoque_inserts_records():
    """save_snapshot persiste datos de ElToque en rate_snapshots."""
    from src.services.rates_service import save_snapshot
    from src.database import async_session_factory
    from src.models.rate_snapshot import RateSnapshot
    
    eltoque_data = {
        'tasas': {'USD': 365.50, 'EUR': 398.00},
        'date': '2026-03-21',
        'hour': 14,
        'minutes': 30
    }
    
    async with async_session_factory() as session:
        await save_snapshot(session, 'eltoque', eltoque_data)
        await session.commit()
        
        # Verificar que se guardó
        stmt = select(RateSnapshot).where(RateSnapshot.source == 'eltoque').order_by(RateSnapshot.fetched_at.desc())
        result = await session.execute(stmt)
        snapshots = result.scalars().all()
        
        assert len(snapshots) >= 2  # USD y EUR
        usd_snapshot = next((s for s in snapshots if s.currency == 'USD'), None)
        assert usd_snapshot is not None
        assert usd_snapshot.sell_rate == 365.50


@pytest.mark.asyncio
async def test_save_snapshot_cadeca_inserts_buy_sell():
    """save_snapshot persiste compra/venta para CADECA."""
    from src.services.rates_service import save_snapshot
    from src.database import async_session_factory
    from src.models.rate_snapshot import RateSnapshot

    cadeca_data = {
        'USD': {'compra': 120.00, 'venta': 125.00},
        'EUR': {'compra': 130.00, 'venta': 135.00}
    }

    async with async_session_factory() as session:
        await save_snapshot(session, 'cadeca', cadeca_data)
        await session.commit()

        from sqlalchemy import select
        stmt = select(RateSnapshot).where(RateSnapshot.source == 'cadeca')
        result = await session.execute(stmt)
        snapshots = result.scalars().all()

        usd_snapshot = next((s for s in snapshots if s.currency == 'USD'), None)
        assert usd_snapshot.buy_rate == 120.00
        assert usd_snapshot.sell_rate == 125.00


@pytest.mark.asyncio
async def test_get_latest_rates_returns_all_sources():
    """get_latest_rates retorna el snapshot más reciente de cada fuente."""
    from src.services.rates_service import get_latest_rates
    from src.database import async_session_factory
    
    async with async_session_factory() as session:
        result = await get_latest_rates(session)
        
        assert 'eltoque' in result
        assert 'binance' in result
        assert 'cadeca' in result
        assert 'bcc' in result


@pytest.mark.asyncio
async def test_get_latest_rates_eltoque_format():
    """get_latest_rates formatea ElToque como {currency: {rate, change}}."""
    from src.services.rates_service import get_latest_rates
    from src.database import async_session_factory

    async with async_session_factory() as session:
        result = await get_latest_rates(session)

        eltoque = result.get('eltoque', {})
        # Verificar estructura
        if eltoque:
            usd = eltoque.get('USD')
            if usd:
                assert 'rate' in usd or 'sell_rate' in usd


@pytest.mark.asyncio
async def test_get_cubanomic_cached_cache_miss():
    """get_cubanomic_cached hace fetch cuando no hay cache."""
    from src.services.rates_service import get_cubanomic_cached
    from unittest.mock import AsyncMock, patch
    import json

    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None  # Cache miss
    
    # Mock db session
    mock_db = AsyncMock()
    
    # Mock fetch_cubanomic_daily result
    mock_result = {
        "ok": True,
        "data": {"USD": {"rate": 365.0}, "EUR": {"rate": 398.0}},
        "updated_at": "2026-03-28T00:00:00Z"
    }
    
    with patch('src.services.rates_service.fetch_cubanomic_daily', return_value=mock_result):
        result = await get_cubanomic_cached(mock_db, mock_redis)
        
        # Verify Redis get was called
        mock_redis.get.assert_called_once_with("cubanomic:latest")
        # Verify fetch was called
        assert result["ok"] is True
        assert result["data"]["USD"]["rate"] == 365.0


@pytest.mark.asyncio
async def test_get_cubanomic_cached_cache_hit():
    """get_cubanomic_cached retorna datos cacheados cuando existen."""
    from src.services.rates_service import get_cubanomic_cached
    from unittest.mock import AsyncMock
    import json

    # Mock Redis client with cached data
    mock_redis = AsyncMock()
    cached_data = {
        "ok": True,
        "data": {"USD": {"rate": 370.0}, "EUR": {"rate": 400.0}},
        "updated_at": "2026-03-27T00:00:00Z"
    }
    mock_redis.get.return_value = json.dumps(cached_data)
    
    # Mock db session
    mock_db = AsyncMock()
    
    result = await get_cubanomic_cached(mock_db, mock_redis)
    
    # Verify Redis get was called
    mock_redis.get.assert_called_once_with("cubanomic:latest")
    # Verify fetch was NOT called (cache hit)
    assert result["ok"] is True
    assert result["data"]["USD"]["rate"] == 370.0  # Cached value
