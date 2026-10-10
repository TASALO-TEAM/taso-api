"""Middleware de autenticación para endpoints admin."""

import hmac

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from src.config import get_settings


API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(api_key: str | None = Depends(API_KEY_HEADER)) -> str:
    """
    Dependencia FastAPI que valida el header X-API-Key.

    Args:
        api_key: API key proporcionada en el header X-API-Key

    Returns:
        str: API key válida

    Raises:
        HTTPException: 401 si la key es inválida o faltante
    """
    settings = get_settings()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key header is required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not hmac.compare_digest(
        api_key.encode("utf-8"), settings.admin_api_key.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key


async def require_auth(api_key: str = Depends(get_api_key)) -> bool:
    """
    Dependencia que requiere autenticación válida.

    Returns:
        bool: True si la autenticación es válida

    Raises:
        HTTPException: 401 si la autenticación falla
    """
    return api_key is not None


async def require_auth_user_endpoints(
    api_key: str | None = Depends(API_KEY_HEADER),
) -> None:
    """
    Dependencia para los endpoints "de usuario" (/images/alerts*,
    /year/subscriptions/me/*, /tspl/subscriptions/me/*).

    Con REQUIRE_KEY_USER_ENDPOINTS=false (por defecto) no cambia nada: siguen
    siendo públicos. Con true exige X-API-Key válida, igual que los endpoints
    admin; así solo los clientes de confianza (taso-bot y la miniapp, que
    fuerza el user_id desde el initData validado) pueden tocarlos.
    """
    if not get_settings().require_key_user_endpoints:
        return None
    await get_api_key(api_key)
    return None
