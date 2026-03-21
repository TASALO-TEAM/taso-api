"""ElToque API client for fetching exchange rates."""

import json
import httpx
from typing import Optional, Dict, Any


async def fetch_eltoque(
    api_key: str,
    api_url: str = "https://tasas.eltoque.com/v1/trmi",
    timeout: float = 10.0
) -> Optional[Dict[str, Any]]:
    """
    Obtiene las tasas de cambio de la API de ElToque.
    
    Args:
        api_key: API key para autenticación (Bearer token)
        api_url: URL de la API
        timeout: Timeout en segundos para la petición
        
    Returns:
        Dict con los datos de tasas o None si hay error
    """
    if not api_key:
        return None
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            pass
        return None
    except httpx.ReadTimeout:
        return None
    except httpx.RequestError:
        return None
    except (KeyError, json.JSONDecodeError):
        return None
