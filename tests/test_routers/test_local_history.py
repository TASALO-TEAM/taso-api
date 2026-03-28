"""Tests for local history endpoint."""

import pytest
from datetime import datetime, timedelta, timezone

from src.database import async_session_factory, DATABASE_URL, get_engine
from src.models.rates import HistorySnapshot


@pytest.fixture
async def db_session():
    """Crear sesión de base de datos para tests."""
    # Initialize engine if not already done
    if async_session_factory is None:
        get_engine(DATABASE_URL, echo=False)
    
    async with async_session_factory() as session:
        yield session
        await session.rollback()


@pytest.mark.asyncio
async def test_local_history_invalid_days(client):
    """Local history endpoint rejects invalid days parameter."""
    # days=0 is below minimum (ge=1)
    response = client.get("/api/v1/tasas/history/local?days=0")
    assert response.status_code == 422  # Validation error

    # days=731 is above maximum (le=730)
    response = client.get("/api/v1/tasas/history/local?days=731")
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_local_history_empty_data(client):
    """Local history endpoint returns empty array when no data."""
    # No data inserted
    response = client.get("/api/v1/tasas/history/local?days=7")

    assert response.status_code == 200
    data = response.json()
    assert data['ok'] is True
    assert data['count'] == 0
    assert data['data'] == []


@pytest.mark.asyncio
async def test_local_history_source_field(client):
    """Local history endpoint returns source='local'."""
    response = client.get("/api/v1/tasas/history/local?days=1")

    assert response.status_code == 200
    data = response.json()
    assert data['source'] == 'local'


@pytest.mark.asyncio
async def test_local_history_response_structure(client):
    """Local history endpoint returns correct structure."""
    response = client.get("/api/v1/tasas/history/local?days=1")

    assert response.status_code == 200
    data = response.json()
    
    assert 'ok' in data
    assert 'data' in data
    assert 'count' in data
    assert 'source' in data
    assert isinstance(data['data'], list)
    assert isinstance(data['count'], int)
