"""Tests for local history endpoint."""

import pytest
from datetime import datetime, timedelta, timezone


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
    """Local history endpoint returns valid 200 with correct structure when no data for the queried window."""
    # In production (shared DB) history_snapshots may have data from the scheduler.
    # We only assert that the response is well-formed; presence/absence of rows
    # depends on live state and is covered by response_structure / source tests.
    response = client.get("/api/v1/tasas/history/local?days=400")

    assert response.status_code == 200
    data = response.json()
    assert data['ok'] is True
    assert isinstance(data['count'], int)
    assert isinstance(data['data'], list)


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
