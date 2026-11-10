"""Fixtures compartidos para tests."""

import os

import pytest
from httpx import Request, Response
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# TestClient ejecuta el lifespan real: con un .env local, notify() le escribiria
# al grupo de soporte de verdad. Vacios, notify() sale por su guard.
os.environ["LOG_BOT_TOKEN"] = ""
os.environ["LOG_CHAT_ID"] = ""

from src.database import Base
from src.main import app


@pytest.fixture
def client():
    """Crear cliente de test para endpoints."""
    from starlette.testclient import TestClient
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def db_session():
    """Crear sesión de DB en memoria para tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def mock_httpx_response():
    """Factory para crear respuestas mock de httpx."""

    def _create_response(
        status_code: int = 200,
        json_data: dict = None,
        text_data: str = None,
        headers: dict = None,
    ):
        request = Request("GET", "https://example.com")
        return Response(
            status_code=status_code,
            json=json_data,
            text=text_data,
            headers=headers or {},
            request=request,
        )

    return _create_response


@pytest.fixture
def eltoque_sample_data() -> dict:
    """Datos de ejemplo de ElToque para tests."""
    return {
        "fecha": "2026-03-21",
        "hora": 14,
        "minutos": 30,
        "tasas": {
            "USD": 365.00,
            "ECU": 398.00,
            "MLC": 210.00,
            "BTC": 9850.50,
            "TRX": 0.25,
            "USDT_TRC20": 362.00,
        },
        "provincias": {"La Habana": {"tasa": 366.00}, "Santiago": {"tasa": 364.50}},
    }


@pytest.fixture
def binance_sample_data() -> list:
    """Datos de ejemplo de Binance US para tests."""
    return [
        {"symbol": "BTCUSDT", "price": "67500.00"},
        {"symbol": "ETHUSDT", "price": "3450.00"},
        # USDTUSDT no disponible en Binance US
    ]


@pytest.fixture(autouse=True)
def _clear_rates_cache():
    """La caché en memoria de lecturas de tasas es de proceso: aislarla entre tests."""
    from src.services import rates_service

    rates_service.invalidate_rates_cache()
    yield
    rates_service.invalidate_rates_cache()
