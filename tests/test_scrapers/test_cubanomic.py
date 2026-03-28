"""Tests for Cubanomic API scraper."""

import pytest
from unittest.mock import AsyncMock, patch
from httpx import Request, Response

from src.scrapers.cubanomic import fetch_cubanomic, _parse_cubanomic_response, _calculate_change


class TestCubanomicParser:
    """Tests for _parse_cubanomic_response function."""
    
    def test_parse_valid_response(self):
        """_parse_cubanomic_response parses valid response correctly."""
        sample_data = {
            "data": {
                "datasets": [
                    {
                        "label": "USD",
                        "data": [
                            {"x": "2026-03-27", "y": 516.04},
                            {"x": "2026-03-28", "y": 517.26}
                        ]
                    },
                    {
                        "label": "EUR",
                        "data": [
                            {"x": "2026-03-27", "y": 582.18},
                            {"x": "2026-03-28", "y": 582.36}
                        ]
                    },
                    {
                        "label": "MLC",
                        "data": [
                            {"x": "2026-03-27", "y": 392.78},
                            {"x": "2026-03-28", "y": 394.82}
                        ]
                    }
                ]
            },
            "updated_at": "2026-03-28T00:00:00.083Z"
        }
        
        result = _parse_cubanomic_response(sample_data)
        
        assert result is not None
        assert result["ok"] is True
        assert "USD" in result["data"]
        assert "EUR" in result["data"]
        assert "MLC" in result["data"]
        
        # Check USD data
        assert result["data"]["USD"]["rate"] == 517.26
        assert result["data"]["USD"]["change"] == "up"
        assert result["data"]["USD"]["prev_rate"] == 516.04
        
        # Check EUR data
        assert result["data"]["EUR"]["rate"] == 582.36
        assert result["data"]["EUR"]["change"] == "up"
        assert result["data"]["EUR"]["prev_rate"] == 582.18
        
        # Check MLC data
        assert result["data"]["MLC"]["rate"] == 394.82
        assert result["data"]["MLC"]["change"] == "up"
        assert result["data"]["MLC"]["prev_rate"] == 392.78
        
        assert result["updated_at"] == "2026-03-28T00:00:00.083Z"
        assert len(result["history"]) == 6  # 3 currencies * 2 data points
    
    def test_parse_multiple_data_points(self):
        """_parse_cubanomic_response handles multiple historical data points."""
        sample_data = {
            "data": {
                "datasets": [
                    {
                        "label": "USD",
                        "data": [
                            {"x": "2026-03-25", "y": 515.00},
                            {"x": "2026-03-26", "y": 515.50},
                            {"x": "2026-03-27", "y": 516.04},
                            {"x": "2026-03-28", "y": 517.26}
                        ]
                    }
                ]
            },
            "updated_at": "2026-03-28T00:00:00.083Z"
        }
        
        result = _parse_cubanomic_response(sample_data)
        
        assert result is not None
        assert result["data"]["USD"]["rate"] == 517.26
        assert result["data"]["USD"]["prev_rate"] == 516.04
        assert result["data"]["USD"]["change"] == "up"
        assert len(result["history"]) == 4
    
    def test_parse_empty_response(self):
        """_parse_cubanomic_response returns None for empty datasets."""
        sample_data = {
            "data": {
                "datasets": []
            },
            "updated_at": "2026-03-28T00:00:00.083Z"
        }
        
        result = _parse_cubanomic_response(sample_data)
        
        assert result is None
    
    def test_parse_missing_data(self):
        """_parse_cubanomic_response returns None for missing required fields."""
        # Missing "data" key
        assert _parse_cubanomic_response({}) is None
        
        # Missing "datasets" key
        assert _parse_cubanomic_response({"data": {}}) is None
        
        # Empty data points
        sample_data = {
            "data": {
                "datasets": [
                    {
                        "label": "USD",
                        "data": []
                    }
                ]
            }
        }
        result = _parse_cubanomic_response(sample_data)
        assert result is None


class TestCubanomicFetcher:
    """Tests for fetch_cubanomic function."""
    
    @pytest.mark.asyncio
    async def test_fetch_success(self, monkeypatch):
        """fetch_cubanomic successfully fetches and parses data."""
        sample_response = {
            "data": {
                "datasets": [
                    {
                        "label": "USD",
                        "data": [
                            {"x": "2026-03-27", "y": 516.04},
                            {"x": "2026-03-28", "y": 517.26}
                        ]
                    },
                    {
                        "label": "EUR",
                        "data": [
                            {"x": "2026-03-27", "y": 582.18},
                            {"x": "2026-03-28", "y": 582.36}
                        ]
                    },
                    {
                        "label": "MLC",
                        "data": [
                            {"x": "2026-03-27", "y": 392.78},
                            {"x": "2026-03-28", "y": 394.82}
                        ]
                    }
                ]
            },
            "updated_at": "2026-03-28T00:00:00.083Z"
        }
        
        mock_response = Response(
            status_code=200,
            json=sample_response,
            request=Request("GET", "https://iframe.cubanomic.com/api/chart?days=30")
        )
        
        async def mock_get(*args, **kwargs):
            return mock_response
        
        monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
        
        result = await fetch_cubanomic(days=30, timeout=15)
        
        assert result["ok"] is True
        assert "USD" in result["data"]
        assert "EUR" in result["data"]
        assert "MLC" in result["data"]
        assert result["data"]["USD"]["rate"] == 517.26
    
    @pytest.mark.asyncio
    async def test_fetch_timeout(self, monkeypatch):
        """fetch_cubanomic handles timeout errors."""
        import httpx
        
        async def mock_get(*args, **kwargs):
            raise httpx.ReadTimeout("Request timed out")
        
        monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
        
        result = await fetch_cubanomic(days=30, timeout=15)
        
        assert result["ok"] is False
        assert result["error"]["code"] == 504
        assert "Timeout" in result["error"]["message"]
    
    @pytest.mark.asyncio
    async def test_fetch_http_error(self, monkeypatch):
        """fetch_cubanomic handles HTTP errors."""
        import httpx
        
        mock_response = Response(
            status_code=500,
            text="Internal Server Error",
            request=Request("GET", "https://iframe.cubanomic.com/api/chart?days=30")
        )
        
        async def mock_get(*args, **kwargs):
            raise httpx.HTTPStatusError(
                "500 Internal Server Error",
                request=Request("GET", "https://iframe.cubanomic.com/api/chart"),
                response=mock_response
            )
        
        monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
        
        result = await fetch_cubanomic(days=30, timeout=15)
        
        assert result["ok"] is False
        assert result["error"]["code"] == 500


class TestCubanomicValidation:
    """Tests for input validation."""
    
    @pytest.mark.asyncio
    async def test_invalid_days_range(self):
        """fetch_cubanomic validates days parameter range."""
        # Days too low
        result = await fetch_cubanomic(days=5)
        assert result["ok"] is False
        assert result["error"]["code"] == 400
        assert "Días inválidos" in result["error"]["message"]
        
        # Days too high
        result = await fetch_cubanomic(days=800)
        assert result["ok"] is False
        assert result["error"]["code"] == 400
        assert "Días inválidos" in result["error"]["message"]
    
    @pytest.mark.asyncio
    async def test_valid_days_range(self, monkeypatch):
        """fetch_cubanomic accepts valid days range."""
        sample_response = {
            "data": {
                "datasets": [
                    {
                        "label": "USD",
                        "data": [
                            {"x": "2026-03-28", "y": 517.26}
                        ]
                    }
                ]
            },
            "updated_at": "2026-03-28T00:00:00.083Z"
        }
        
        mock_response = Response(
            status_code=200,
            json=sample_response,
            request=Request("GET", "https://iframe.cubanomic.com/api/chart")
        )
        
        async def mock_get(*args, **kwargs):
            return mock_response
        
        monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
        
        # Test minimum valid days
        result = await fetch_cubanomic(days=7)
        assert result["ok"] is True
        
        # Test maximum valid days
        result = await fetch_cubanomic(days=730)
        assert result["ok"] is True


class TestChangeCalculation:
    """Tests for _calculate_change function."""
    
    def test_change_up(self):
        """_calculate_change returns 'up' when rate increases."""
        assert _calculate_change(517.26, 516.04) == "up"
        assert _calculate_change(100.0, 99.0) == "up"
    
    def test_change_down(self):
        """_calculate_change returns 'down' when rate decreases."""
        assert _calculate_change(516.04, 517.26) == "down"
        assert _calculate_change(99.0, 100.0) == "down"
    
    def test_change_neutral(self):
        """_calculate_change returns 'neutral' when rate is unchanged."""
        assert _calculate_change(517.26, 517.26) == "neutral"
        assert _calculate_change(100.0, 100.0) == "neutral"
    
    def test_change_none_previous(self):
        """_calculate_change returns 'neutral' when previous is None."""
        assert _calculate_change(517.26, None) == "neutral"
