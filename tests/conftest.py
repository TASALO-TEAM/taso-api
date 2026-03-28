"""Fixtures compartidos para tests."""

import pytest
from httpx import Request, Response


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


@pytest.fixture
def cadeca_sample_html() -> str:
    """HTML de ejemplo de CADECA para tests (estructura con tabla y headers)."""
    return """
    <html>
    <body>
        <table class="table table-bordered">
            <thead>
                <tr>
                    <th>No.</th>
                    <th>Moneda</th>
                    <th>Compra</th>
                    <th>Venta</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>1</td>
                    <td>USD</td>
                    <td class="text-right">120.00</td>
                    <td class="text-right">125.00</td>
                </tr>
                <tr>
                    <td>2</td>
                    <td>EUR</td>
                    <td class="text-right">130.00</td>
                    <td class="text-right">135.00</td>
                </tr>
            </tbody>
        </table>
    </body>
    </html>
    """
