"""Integration test para verificar el flujo completo del histórico de Cubanomic."""

import pytest
from unittest.mock import AsyncMock, patch

from src.main import app
from starlette.testclient import TestClient


@pytest.fixture
def client():
    """Crear cliente de test para endpoints."""
    with TestClient(app) as client:
        yield client


class TestCubanomicHistoryIntegration:
    """Tests de integración para el histórico de Cubanomic."""

    def test_full_flow_mocked_api_response(self, client):
        """
        Test de integración completo: API → Endpoint → Response → Frontend format.
        
        Simula la respuesta completa de la API de Cubanomic y verifica que
        el endpoint retorne los datos en el formato que el frontend espera.
        """
        # Mock data simulating real Cubanomic API response
        mock_cubanomic_response = {
            "ok": True,
            "history": [
                {"date": "2026-03-20T00:00:00Z", "currency": "USD", "rate": 515.50},
                {"date": "2026-03-20T00:00:00Z", "currency": "EUR", "rate": 580.25},
                {"date": "2026-03-20T00:00:00Z", "currency": "MLC", "rate": 390.00},
                {"date": "2026-03-21T00:00:00Z", "currency": "USD", "rate": 516.00},
                {"date": "2026-03-21T00:00:00Z", "currency": "EUR", "rate": 581.50},
                {"date": "2026-03-21T00:00:00Z", "currency": "MLC", "rate": 391.25},
                {"date": "2026-03-22T00:00:00Z", "currency": "USD", "rate": 516.50},
                {"date": "2026-03-22T00:00:00Z", "currency": "EUR", "rate": 582.00},
                {"date": "2026-03-22T00:00:00Z", "currency": "MLC", "rate": 392.50},
            ]
        }

        with patch('src.scrapers.cubanomic.fetch_cubanomic', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_cubanomic_response

            with patch('src.redis_client.RedisClient.get', new_callable=AsyncMock, return_value=None):
                with patch('src.redis_client.RedisClient.set', new_callable=AsyncMock):
                    response = client.get("/api/v1/tasas/history/cubanomic?days=7")
                    assert response.status_code == 200

                    data = response.json()

                    # Verify top-level structure
                    assert data["ok"] is True
                    assert "data" in data
                    assert "count" in data
                    assert data["count"] == 3  # 3 days of data

                    # Verify data is grouped by date (3 days, not 9 currency entries)
                    assert len(data["data"]) == 3, f"Expected 3 data points (one per day), got {len(data['data'])}"

                    # Verify each data point has all required fields
                    for i, point in enumerate(data["data"]):
                        assert "fetched_at" in point, f"Point {i} missing fetched_at"
                        assert "usd_rate" in point, f"Point {i} missing usd_rate"
                        assert "eur_rate" in point, f"Point {i} missing eur_rate"
                        assert "mlc_rate" in point, f"Point {i} missing mlc_rate"

                        # Verify rates are not None
                        assert point["usd_rate"] is not None, f"Point {i} usd_rate is None"
                        assert point["eur_rate"] is not None, f"Point {i} eur_rate is None"
                        assert point["mlc_rate"] is not None, f"Point {i} mlc_rate is None"

                    # Verify specific values for first day (2026-03-20)
                    first_day = data["data"][0]
                    assert first_day["usd_rate"] == 515.50
                    assert first_day["eur_rate"] == 580.25
                    assert first_day["mlc_rate"] == 390.00

                    # Verify specific values for last day (2026-03-22)
                    last_day = data["data"][2]
                    assert last_day["usd_rate"] == 516.50
                    assert last_day["eur_rate"] == 582.00
                    assert last_day["mlc_rate"] == 392.50

                    # Verify dates are in correct format (ISO 8601)
                    assert "2026-03-20" in first_day["fetched_at"]
                    assert "2026-03-22" in last_day["fetched_at"]

    def test_frontend_javascript_compatibility(self, client):
        """
        Verifica que la respuesta sea compatible con el código JavaScript del frontend.
        
        El frontend espera este formato:
        ```javascript
        const history = data.data.map(point => ({
          fetched_at: point.fetched_at,
          usdRate: point.usd_rate,
          eurRate: point.eur_rate,
          mlcRate: point.mlc_rate
        }));
        ```
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

                    # Simulate frontend JavaScript parsing
                    history = []
                    for point in data["data"]:
                        parsed_point = {
                            "fetched_at": point["fetched_at"],
                            "usdRate": point["usd_rate"] or point["buy_rate"] or point["sell_rate"] or 0,
                            "eurRate": point["eur_rate"] or point["buy_rate"] or point["sell_rate"] or 0,
                            "mlcRate": point["mlc_rate"] or point["buy_rate"] or point["sell_rate"] or 0
                        }
                        history.append(parsed_point)

                    # Verify parsed data structure matches what charts expect
                    assert len(history) == 2, "Should have 2 data points"

                    # First data point (2026-03-27)
                    assert history[0]["usdRate"] == 516.04
                    assert history[0]["eurRate"] == 582.18
                    assert history[0]["mlcRate"] == 392.78

                    # Second data point (2026-03-28)
                    assert history[1]["usdRate"] == 517.26
                    assert history[1]["eurRate"] == 582.36
                    assert history[1]["mlcRate"] == 394.82
