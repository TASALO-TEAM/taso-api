"""Tests para el middleware de autenticación."""

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.middleware.auth import get_api_key


class TestAuthMiddleware:
    """Tests para las dependencias de autenticación."""

    def test_get_api_key_missing_returns_401(self):
        """API key faltante debe retornar 401."""
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint(api_key: str = Depends(get_api_key)):
            return {"api_key": api_key}
        
        with TestClient(app) as client:
            response = client.get("/test")
        
        assert response.status_code == 401
        assert response.json()["detail"] == "X-API-Key header is required"

    def test_get_api_key_invalid_returns_401(self):
        """API key inválida debe retornar 401."""
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint(api_key: str = Depends(get_api_key)):
            return {"api_key": api_key}
        
        with TestClient(app) as client:
            response = client.get("/test", headers={"X-API-Key": "wrong_key"})
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid API key"
