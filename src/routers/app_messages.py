"""Router para los mensajes de la app Android (sección Alertas).

Endpoint público (sin auth): lo consulta la app con GET /api/v1/app/messages.
Endpoints admin (X-API-Key): gestión desde /msapp en taso-bot.

Mismo patrón que el sistema de anuncios (routers/ads.py).
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.middleware.auth import require_auth
from src.schemas.app_message import (
    AppMessageAPIResponse,
    AppMessageCreateSchema,
    AppMessagePublicSchema,
    AppMessageSchema,
    AppMessageUpdateSchema,
)
from src.services import app_message_service

logger = logging.getLogger(__name__)

# Router público: sin dependencies de auth (mismo criterio que routers/ads.py y routers/rates.py)
router = APIRouter()

# Router admin: requiere X-API-Key en todos sus endpoints
admin_router = APIRouter(dependencies=[Depends(require_auth)])


# ── Endpoint público (sin auth) ──────────────────────────────────────────────


@router.get("/messages", response_model=AppMessageAPIResponse)
async def get_messages_endpoint(
    limit: int = Query(default=5, ge=1, le=20, description="Máximo de mensajes (los más nuevos)"),
    since_id: int = Query(default=0, ge=0, description="Solo mensajes con id mayor que este"),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Últimos mensajes activos, los más nuevos primero (schema público, sin campos sensibles).

    data=[] si no hay ninguno (no es un error). Con since_id la app comprueba si hay algo nuevo
    con una respuesta mínima.
    """
    messages = await app_message_service.list_messages(db, limit=limit, since_id=since_id, active_only=True)
    return AppMessageAPIResponse(
        ok=True,
        data=[AppMessagePublicSchema.model_validate(m) for m in messages],
        count=len(messages),
    )


# ── Endpoints admin (X-API-Key) ──────────────────────────────────────────────


@admin_router.get("/messages/all", response_model=AppMessageAPIResponse)
async def list_all_messages_endpoint(
    limit: int = Query(default=20, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Lista los últimos mensajes, activos o no. Uso: gestión desde /msapp."""
    messages = await app_message_service.list_messages(db, limit=limit, active_only=False)
    return AppMessageAPIResponse(
        ok=True,
        data=[AppMessageSchema.model_validate(m) for m in messages],
        count=len(messages),
    )


@admin_router.post("/messages", response_model=AppMessageAPIResponse)
async def create_message_endpoint(
    body: AppMessageCreateSchema,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Publica un mensaje nuevo en la app."""
    message = await app_message_service.create_message(
        db,
        title=body.title,
        body=body.body,
        format=body.format,
        created_by=body.created_by,
    )
    if not message:
        return AppMessageAPIResponse(
            ok=False,
            error={"code": 500, "message": "Error al guardar el mensaje en la base de datos"},
        )
    return AppMessageAPIResponse(ok=True, data=AppMessageSchema.model_validate(message), count=1)


@admin_router.patch("/messages/{message_id}", response_model=AppMessageAPIResponse)
async def update_message_endpoint(
    message_id: int,
    body: AppMessageUpdateSchema,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Edita un mensaje: título, cuerpo, formato o activo/inactivo (retirarlo sin borrarlo)."""
    message = await app_message_service.update_message(
        db,
        message_id=message_id,
        title=body.title,
        body=body.body,
        format=body.format,
        is_active=body.is_active,
    )
    if not message:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    return AppMessageAPIResponse(ok=True, data=AppMessageSchema.model_validate(message), count=1)


@admin_router.delete("/messages/{message_id}", response_model=AppMessageAPIResponse)
async def delete_message_endpoint(
    message_id: int,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Elimina un mensaje definitivamente."""
    deleted = await app_message_service.delete_message(db, message_id=message_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    return AppMessageAPIResponse(ok=True, data={"deleted": True, "message_id": message_id}, count=1)
