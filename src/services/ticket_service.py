"""Service para gestión del sistema de tickets (soporte/contacto usuario→admin)."""

import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ticket import Ticket

logger = logging.getLogger(__name__)


async def create_ticket(
    db: AsyncSession,
    user_id: int,
    kind: str,
    message: str,
    username: Optional[str] = None,
) -> Optional[Ticket]:
    """Crea un ticket nuevo (status='open' por defecto)."""
    ticket = Ticket(
        user_id=user_id,
        username=username,
        kind=kind,
        message=message,
        status="open",
    )
    try:
        db.add(ticket)
        await db.commit()
        await db.refresh(ticket)
        logger.info("✅ Ticket created: id=%d kind=%s user_id=%d", ticket.id, kind, user_id)
        return ticket
    except Exception as e:
        logger.error("DB error in create_ticket: %s", e, exc_info=True)
        await db.rollback()
        return None


async def get_ticket(db: AsyncSession, ticket_id: int) -> Optional[Ticket]:
    """Obtiene un ticket por id."""
    stmt = select(Ticket).where(Ticket.id == ticket_id)
    try:
        result = await db.execute(stmt)
        return result.scalars().first()
    except Exception as e:
        logger.error("DB error in get_ticket id=%d: %s", ticket_id, e)
        return None


async def list_tickets(
    db: AsyncSession,
    status: Optional[str] = None,
    kind: Optional[str] = None,
) -> List[Ticket]:
    """Lista tickets, opcionalmente filtrados por status y/o kind.

    Orden: más recientes primero (created_at desc), para que /tkts
    en el bot muestre lo más urgente arriba.
    """
    stmt = select(Ticket)
    if status is not None:
        stmt = stmt.where(Ticket.status == status)
    if kind is not None:
        stmt = stmt.where(Ticket.kind == kind)
    stmt = stmt.order_by(Ticket.created_at.desc())
    try:
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception as e:
        logger.error("DB error in list_tickets: %s", e)
        return []


async def update_ticket(
    db: AsyncSession,
    ticket_id: int,
    status: Optional[str] = None,
    claimed_by: Optional[int] = None,
) -> Optional[Ticket]:
    """Edita status y/o claimed_by de un ticket existente.

    Solo actualiza los campos != None. Si se pasa claimed_by y el ticket
    sigue 'open', lo mueve automáticamente a 'in_progress' (a menos que el
    caller ya haya especificado explícitamente otro status).
    """
    ticket = await get_ticket(db, ticket_id)
    if not ticket:
        return None
    try:
        if claimed_by is not None:
            ticket.claimed_by = claimed_by
            if status is None and ticket.status == "open":
                ticket.status = "in_progress"
        if status is not None:
            ticket.status = status
        await db.commit()
        await db.refresh(ticket)
        logger.info("✏️ Ticket updated: id=%d status=%s", ticket_id, ticket.status)
        return ticket
    except Exception as e:
        logger.error("DB error in update_ticket id=%d: %s", ticket_id, e, exc_info=True)
        await db.rollback()
        return None
