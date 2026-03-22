"""Middleware de autenticación para endpoints admin."""

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

    if api_key != settings.admin_api_key:
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
