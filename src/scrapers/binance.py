"""Binance API client for fetching cryptocurrency prices."""

import json
import httpx
from typing import Optional, Dict, Any, List


DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "USDTUSDT"]


async def fetch_binance(
    symbols: Optional[List[str]] = None,
    base_url: str = "https://api.binance.com/api/v3/ticker/price",
    timeout: float = 10.0
) -> Optional[Dict[str, float]]:
    """
    Obtiene precios de criptomonedas de Binance.
    
    Args:
        symbols: Lista de símbolos a consultar (default: BTC, ETH, USDT)
        base_url: URL base de la API de Binance
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
