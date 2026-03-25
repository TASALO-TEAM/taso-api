"""Binance API client for fetching cryptocurrency prices."""

import json
import httpx
from typing import Optional, Dict, Any, List


# Binance global API con más pares de criptomonedas
BINANCE_GLOBAL_URL = "https://api.binance.com/api/v3/ticker/price"

# Símbolos principales para el ticker (top criptomonedas vs USDT)
# Incluye USDTUSDT para referencia del valor del USDT
DEFAULT_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "SOLUSDT", "TRXUSDT", "DOTUSDT", "MATICUSDT",
    "AVAXUSDT", "LINKUSDT", "UNIUSDT", "ATOMUSDT", "LTCUSDT",
    "BCHUSDT", "FILUSDT", "ETCUSDT", "XLMUSDT", "ALGOUSDT",
    "USDTUSDT"  # Para referencia del valor del USDT
]


async def fetch_binance(
    symbols: Optional[List[str]] = None,
    base_url: str = BINANCE_GLOBAL_URL,
    timeout: float = 10.0
) -> Optional[Dict[str, float]]:
    """
    Obtiene precios de criptomonedas de Binance (API global).

    Args:
        symbols: Lista de símbolos a consultar (default: top 20 criptomonedas vs USDT)
        base_url: URL base de la API de Binance (default: api.binance.com)
        timeout: Timeout en segundos

    Returns:
        Dict con símbolo -> precio o None si hay error
    """
    symbols = symbols or DEFAULT_SYMBOLS

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(base_url, timeout=timeout)
            response.raise_for_status()
            data: List[Dict[str, str]] = response.json()

            result = {}
            for item in data:
                symbol = item.get("symbol")
                if symbol in symbols:
                    # Extraer precio como float
                    result[symbol] = float(item.get("price", 0))

            return result

    except httpx.HTTPStatusError:
        return None
    except httpx.ReadTimeout:
        return None
    except httpx.RequestError:
        return None
    except (KeyError, ValueError, json.JSONDecodeError):
        return None
