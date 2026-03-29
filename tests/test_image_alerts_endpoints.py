"""Tests for image alert endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app


@pytest.mark.asyncio
async def test_create_alert():
    """Test creating a new alert."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/images/alerts",
            json={
                "user_id": 123456,
                "alert_time": "07:15",
                "format_type": "photo",
                "enabled": True
            }
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["data"]["user_id"] == 123456
    assert data["data"]["alert_time"] == "07:15"


@pytest.mark.asyncio
async def test_get_alert():
    """Test getting an alert."""
    # First create
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post(
            "/api/v1/images/alerts",
            json={
                "user_id": 789012,
                "alert_time": "08:30",
                "format_type": "photo",
                "enabled": True
            }
        )
        
        # Then get
        response = await ac.get("/api/v1/images/alerts/789012")
    
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["data"]["user_id"] == 789012
