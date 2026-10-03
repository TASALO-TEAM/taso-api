"""Service para los mensajes de la app Android (AppMessage)."""

import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.app_message import AppMessage

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 5
MAX_LIMIT = 20


async def create_message(
    db: AsyncSession,
    title: str,
    body: str,
    format: str = "telegram",
    created_by: Optional[int] = None,
) -> Optional[AppMessage]:
    """Crea un mensaje nuevo (activo por defecto)."""
    message = AppMessage(
        title=title,
        body=body,
        format=format,
        created_by=created_by,
        is_active=True,
    )
    try:
        db.add(message)
        await db.commit()
        await db.refresh(message)
        logger.info("App message created: id=%d format=%s", message.id, format)
        return message
    except Exception as e:
        logger.error("DB error in create_message: %s", e, exc_info=True)
        await db.rollback()
        return None


async def list_messages(
    db: AsyncSession,
    limit: int = DEFAULT_LIMIT,
    since_id: int = 0,
    active_only: bool = True,
) -> List[AppMessage]:
    """Lista mensajes, los más nuevos primero.

    Args:
        limit: máximo de mensajes (se acota a 1..MAX_LIMIT).
        since_id: solo mensajes con id mayor (la app lo usa para consultar "¿hay algo nuevo?").
        active_only: si True, oculta los desactivados.
    """
    limit = max(1, min(limit, MAX_LIMIT))
    stmt = select(AppMessage)
    if active_only:
        stmt = stmt.where(AppMessage.is_active.is_(True))
    if since_id > 0:
        stmt = stmt.where(AppMessage.id > since_id)
    stmt = stmt.order_by(AppMessage.id.desc()).limit(limit)
    try:
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception as e:
        logger.error("DB error in list_messages: %s", e)
        return []


async def get_message(db: AsyncSession, message_id: int) -> Optional[AppMessage]:
    """Obtiene un mensaje por id."""
    try:
        result = await db.execute(select(AppMessage).where(AppMessage.id == message_id))
        return result.scalars().first()
    except Exception as e:
        logger.error("DB error in get_message id=%d: %s", message_id, e)
        return None


async def update_message(
    db: AsyncSession,
    message_id: int,
    title: Optional[str] = None,
    body: Optional[str] = None,
    format: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[AppMessage]:
    """Edita los campos indicados. Devuelve None si no existe o falla la base de datos."""
    message = await get_message(db, message_id)
    if message is None:
        return None
    if title is not None:
        message.title = title
    if body is not None:
        message.body = body
    if format is not None:
        message.format = format
    if is_active is not None:
        message.is_active = is_active
    try:
        await db.commit()
        await db.refresh(message)
        return message
    except Exception as e:
        logger.error("DB error in update_message id=%d: %s", message_id, e, exc_info=True)
        await db.rollback()
        return None


async def delete_message(db: AsyncSession, message_id: int) -> bool:
    """Elimina un mensaje definitivamente. False si no existe o falla."""
    message = await get_message(db, message_id)
    if message is None:
        return False
    try:
        await db.delete(message)
        await db.commit()
        return True
    except Exception as e:
        logger.error("DB error in delete_message id=%d: %s", message_id, e, exc_info=True)
        await db.rollback()
        return False
