"""ElToque API client for fetching exchange rates."""

import logging
from typing import Optional, Dict, Any

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)


class ElToqueError(Exception):
    """Fallo al consultar la API de ElToque, con motivo legible.

    `retryable=False` marca errores deterministas (token vencido/inválido,
    clave sin configurar): reintentarlos solo gasta tiempo.
    """

    def __init__(self, reason: str, retryable: bool = True, status: Optional[int] = None):
        super().__init__(reason)
        self.reason = reason
        self.retryable = retryable
        self.status = status


async def fetch_eltoque_strict(
    api_key: Optional[str] = None,
    api_url: Optional[str] = None,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    """Consulta la API de ElToque y devuelve el JSON con `tasas`.

    Lanza ElToqueError con el motivo del fallo (nunca devuelve None).
    """
    if api_key is None or api_url is None:
        settings = get_settings()
        api_key = settings.eltoque_api_key if api_key is None else api_key
        api_url = settings.eltoque_api_url if api_url is None else api_url

    if not api_key:
        raise ElToqueError("ELTOQUE_API_KEY no está configurada", retryable=False)

    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, headers=headers, timeout=timeout)
    except httpx.TimeoutException:
        raise ElToqueError("timeout") from None
    except httpx.RequestError as e:
        raise ElToqueError(f"error de red ({type(e).__name__})") from None

    status = response.status_code
    if status in (401, 403):
        raise ElToqueError(
            f"token inválido o vencido (HTTP {status})", retryable=False, status=status
        )
    if status == 429:
        raise ElToqueError("límite de peticiones (HTTP 429)", status=status)
    if status >= 400:
        raise ElToqueError(f"HTTP {status}", retryable=status >= 500, status=status)

    try:
        data = response.json()
    except ValueError:
        raise ElToqueError("la respuesta no es JSON") from None

    if not isinstance(data, dict):
        raise ElToqueError("respuesta con formato inesperado")
    if not data.get("tasas"):
        # La API responde {"msg": "..."} cuando rechaza la clave aunque el HTTP sea 200
        msg = data.get("msg")
        if msg:
            raise ElToqueError(f"la API respondió: {msg}", retryable=False)
        raise ElToqueError("respuesta sin 'tasas'")
    return data


async def fetch_eltoque(
    api_key: Optional[str] = None,
    api_url: Optional[str] = None,
    timeout: float = 10.0,
) -> Optional[Dict[str, Any]]:
    """Versión tolerante: devuelve los datos o None (deja el motivo en el log)."""
    try:
        return await fetch_eltoque_strict(api_key, api_url, timeout)
    except ElToqueError as e:
        logger.warning("ElToque API: %s", e.reason)
        return None
    except Exception as e:
        logger.error("ElToque API: error inesperado: %s", e)
        return None
