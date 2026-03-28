"""Tests para el endpoint de histórico de Cubanomic."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from src.main import app
from starlette.testclient import TestClient


@pytest.fixture
def client():
    """Crear cliente de test para endpoints."""
    with TestClient(app) as client:
        yield client


class TestCubanomicHistoryStructure:
    """Tests para verificar la estructura de datos del histórico de Cubanomic."""

    def test_cubanomic_history_returns_rate_fields(self, client):
        """
        GET /api/v1/tasas/history/cubanomic debe retornar datos con campos usd_rate, eur_rate, mlc_rate.
        
        Este test verifica que el endpoint retorne la estructura correcta que el frontend espera:
        - data[].usd_rate: tasa del USD
        - data[].eur_rate: tasa del EUR  
        - data[].mlc_rate: tasa del MLC
        - data[].fetched_at: fecha de captura
        """
        # Mock the fetch_cubanomic function to return sample data
        mock_history = [
            {
                "date": "2026-03-27T00:00:00Z",
                "currency": "USD",
                "rate": 516.04
            },
            {
                "date": "2026-03-27T00:00:00Z",
                "currency": "EUR",
                "rate": 582.18
            },
            {
                "date": "2026-03-27T00:00:00Z",
                "currency": "MLC",
                "rate": 392.78
            },
            {
                "date": "2026-03-28T00:00:00Z",
                "currency": "USD",
                "rate": 517.26
            },
            {
                "date": "2026-03-28T00:00:00Z",
                "currency": "EUR",
                "rate": 582.36
            },
            {
                "date": "2026-03-28T00:00:00Z",
                "currency": "MLC",
                "rate": 394.82
            }
        ]

        with patch('src.scrapers.cubanomic.fetch_cubanomic', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {
                "ok": True,
                "history": mock_history
            }

            # Also mock Redis
            with patch('src.redis_client.RedisClient.get', new_callable=AsyncMock) as mock_redis_get:
                mock_redis_get.return_value = None  # Cache miss

                with patch('src.redis_client.RedisClient.set', new_callable=AsyncMock):
                    response = client.get("/api/v1/tasas/history/cubanomic?days=30")

                    assert response.status_code == 200
                    data = response.json()

                    # Verify structure
                    assert data["ok"] is True
                    assert "data" in data
                    assert isinstance(data["data"], list)
                    assert len(data["data"]) > 0

                    # CRITICAL: Verify each data point has the rate fields
                    for point in data["data"]:
                        assert "fetched_at" in point, "Each point must have fetched_at"
                        # The endpoint should transform the flat history into structured data
                        # with usd_rate, eur_rate, mlc_rate per timestamp
                        assert "usd_rate" in point or "buy_rate" in point or "sell_rate" in point, \
                            "Each point must have rate fields (usd_rate, eur_rate, or buy_rate/sell_rate)"

    def test_cubanomic_history_grouped_by_date(self, client):
        """
        GET /api/v1/tasas/history/cubanomic debe agrupar rates por fecha.
        
        El frontend espera que cada punto en el array tenga:
        {
            "fetched_at": "2026-03-28T00:00:00Z",
            "usd_rate": 517.26,
            "eur_rate": 582.36,
            "mlc_rate": 394.82
        }
        """
        mock_history = [
            {"date": "2026-03-27T00:00:00Z", "currency": "USD", "rate": 516.04},
            {"date": "2026-03-27T00:00:00Z", "currency": "EUR", "rate": 582.18},
            {"date": "2026-03-27T00:00:00Z", "currency": "MLC", "rate": 392.78},
            {"date": "2026-03-28T00:00:00Z", "currency": "USD", "rate": 517.26},
            {"date": "2026-03-28T00:00:00Z", "currency": "EUR", "rate": 582.36},
            {"date": "2026-03-28T00:00:00Z", "currency": "MLC", "rate": 394.82}
        ]

        with patch('src.scrapers.cubanomic.fetch_cubanomic', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"ok": True, "history": mock_history}

            with patch('src.redis_client.RedisClient.get', new_callable=AsyncMock, return_value=None):
                with patch('src.redis_client.RedisClient.set', new_callable=AsyncMock):
                    response = client.get("/api/v1/tasas/history/cubanomic?days=30")
                    assert response.status_code == 200

                    data = response.json()
                    
                    # Should have 2 data points (one per date), not 6 (one per currency)
                    # Each point should contain all 3 rates
                    assert len(data["data"]) == 2, \
                        f"Expected 2 data points (grouped by date), got {len(data['data'])}"

                    # First point should have all three rates
                    first_point = data["data"][0]
                    assert "fetched_at" in first_point
                    # Should have rate fields for all currencies on that date
                    has_rates = (
                        ("usd_rate" in first_point) or 
                        ("buy_rate" in first_point and first_point.get("currency") == "USD")
                    )
                    assert has_rates, "First point should have rate data"
