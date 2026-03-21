"""Tests para la configuración de la aplicación."""

import os
import pytest
from pathlib import Path
from src.config import Settings


def test_settings_from_env_vars(monkeypatch):
    """Settings carga correctamente desde variables de entorno."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
    monkeypatch.setenv("ELTOQUE_API_KEY", "test_key_123")
    monkeypatch.setenv("ELTOQUE_API_URL", "https://test.eltoque.com/v1")
    monkeypatch.setenv("ADMIN_API_KEY", "admin_secret_456")
    monkeypatch.setenv("REFRESH_INTERVAL_MINUTES", "10")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://example.com,https://test.com")
    
    settings = Settings()
    
    assert settings.database_url == "sqlite+aiosqlite:///./test.db"
    assert settings.eltoque_api_key == "test_key_123"
    assert settings.eltoque_api_url == "https://test.eltoque.com/v1"
    assert settings.admin_api_key == "admin_secret_456"
    assert settings.refresh_interval_minutes == 10
    assert settings.allowed_origins == "https://example.com,https://test.com"


def test_settings_default_values():
    """Settings usa valores por defecto cuando no hay env."""
    # Crear settings con solo el requerido
    # Nota: los valores default se usan cuando no están en el .env ni como parámetro
    settings = Settings(
        database_url="sqlite+aiosqlite:///./default.db",
        admin_api_key="test_default"  # Override del .env local
    )
    
    assert settings.refresh_interval_minutes == 5  # default
    assert settings.allowed_origins == "*"  # default


def test_settings_invalid_interval():
    """Settings rechaza intervalo inválido."""
    with pytest.raises(ValueError, match="REFRESH_INTERVAL_MINUTES debe ser >= 1"):
        Settings(
            database_url="sqlite+aiosqlite:///./test.db",
            refresh_interval_minutes=0
        )


def test_allowed_origins_list_star():
    """allowed_origins_list retorna ['*'] cuando allowed_origins es '*'."""
    settings = Settings(
        database_url="sqlite+aiosqlite:///./test.db",
        allowed_origins="*"
    )
    
    assert settings.allowed_origins_list == ["*"]


def test_allowed_origins_list_multiple():
    """allowed_origins_list parsea correctamente múltiples orígenes."""
    settings = Settings(
        database_url="sqlite+aiosqlite:///./test.db",
        allowed_origins="https://example.com, https://test.com ,https://api.com"
    )
    
    assert settings.allowed_origins_list == [
        "https://example.com",
        "https://test.com",
        "https://api.com"
    ]
