"""Binance API client for fetching cryptocurrency prices."""

import json
import httpx
from typing import Optional, Dict, Any, List


# Binance US API (funciona desde regiones restringidas)
# Nota: Binance Global (api.binance.com) está bloqueado en algunas regiones
# Binance US tiene menos símbolos pero es accesible
BINANCE_URL = "https://api.binance.us/api/v3/ticker/price"

# Símbolos disponibles en Binance US (verificar periódicamente)
# USDTUSDT no está disponible en Binance US, se usa solo USD como referencia
DEFAULT_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "SOLUSDT", "TRXUSDT", "DOTUSDT", "MATICUSDT",
    "AVAXUSDT", "LINKUSDT", "UNIUSDT", "ATOMUSDT", "LTCUSDT",
    "BCHUSDT", "FILUSDT", "ETCUSDT", "XLMUSDT", "ALGOUSDT"
    # USDTUSDT no disponible en Binance US
]


async def fetch_binance(
    symbols: Optional[List[str]] = None,
    base_url: str = BINANCE_URL,
    timeout: float = 10.0
) -> Optional[Dict[str, float]]:
    """
    Obtiene precios de criptomonedas de Binance US.

    Nota: Binance Global (api.binance.com) está bloqueado en algunas regiones.
    Usamos Binance US (api.binance.us) que es accesible pero tiene menos símbolos.

    Args:
        symbols: Lista de símbolos a consultar (default: top 21 criptomonedas vs USDT)
        base_url: URL base de la API de Binance (default: api.binance.us)
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
                # Filter only the symbols we're interested in
                if symbol in symbols:
                    # Extraer precio como float
                    result[symbol] = float(item.get("price", 0))

            # Log how many symbols we got for debugging
            if len(result) < len(symbols):
                print(f"⚠️ Binance: Solo {len(result)}/{len(symbols)} símbolos obtenidos")
                missing = set(symbols) - set(result.keys())
                if missing:
                    print(f"   Símbolos faltantes: {sorted(missing)[:10]}")  # Show first 10

            return result

    except httpx.HTTPStatusError as e:
        print(f"❌ Binance HTTP error: {e.response.status_code}")
        return None
    except httpx.ReadTimeout:
        print(f"⚠️ Binance timeout ({timeout}s)")
        return None
    except httpx.RequestError as e:
        print(f"❌ Binance request error: {e}")
        return None
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        print(f"❌ Binance parse error: {e}")
        return None
