"""ElToque API client for fetching exchange rates."""

import json
import httpx
from typing import Optional, Dict, Any

from src.config import get_settings


async def fetch_eltoque(
    api_key: Optional[str] = None,
    api_url: Optional[str] = None,
    timeout: float = 10.0
) -> Optional[Dict[str, Any]]:
    """
    Obtiene las tasas de cambio de la API de ElToque.

    Args:
        api_key: API key para autenticación (Bearer token). 
                 Si no se proporciona, se carga desde la configuración.
        api_url: URL de la API. Si no se proporciona, se usa la de configuración.
        timeout: Timeout en segundos para la petición

    Returns:
        Dict con los datos de tasas o None si hay error
    """
    # Cargar configuración si no se proporcionan los parámetros
    if api_key is None or api_url is None:
        settings = get_settings()
        if api_key is None:
            api_key = settings.eltoque_api_key
        if api_url is None:
            api_url = settings.eltoque_api_url

    if not api_key:
        print("❌ Error: ELTOQUE_API_KEY no está configurada")
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
