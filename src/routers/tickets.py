"""Router para el sistema de tickets (soporte/contacto usuario→admin).

Todos los endpoints requieren X-API-Key, igual que routers/alerts.py: los
tickets siempre se crean/gestionan a través de taso-bot (comando /tkt para
crear, notificación a admins para gestionar), nunca directamente por un
usuario sin pasar por el bot. El bot es el único cliente de confianza que
sostiene la admin_key — el hecho de que el ticket lo origine un usuario NO
usuario NO significa que el endpoint deba ser público.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.middleware.auth import require_auth
from src.services import ticket_service
from src.schemas.ticket import (
    TicketSchema,
    TicketCreateSchema,
    TicketUpdateSchema,
    TicketAPIResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_auth)])


@router.post("", response_model=TicketAPIResponse)
async def create_ticket_endpoint(
    body: TicketCreateSchema,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Crea un ticket nuevo. Llamado por taso-bot al enviar /tkt."""
    ticket = await ticket_service.create_ticket(
        db,
        user_id=body.user_id,
        kind=body.kind,
        message=body.message,
        username=body.username,
    )
    if not ticket:
        return TicketAPIResponse(
            ok=False,
            error={"code": 500, "message": "Error al guardar el ticket en la base de datos"},
        )
    return TicketAPIResponse(ok=True, data=TicketSchema.model_validate(ticket), count=1)


@router.get("", response_model=TicketAPIResponse)
async def list_tickets_endpoint(
    status: Optional[str] = Query(default=None),
    kind: Optional[str] = Query(default=None),
    limit: Optional[int] = Query(default=None, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Lista tickets, filtrables por status y/o kind. Uso: /tkt list y /tkt active en taso-bot."""
    tickets = await ticket_service.list_tickets(db, status=status, kind=kind, limit=limit)
    return TicketAPIResponse(
        ok=True,
        data=[TicketSchema.model_validate(t) for t in tickets],
        count=len(tickets),
    )


@router.get("/{ticket_id}", response_model=TicketAPIResponse)
async def get_ticket_endpoint(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Obtiene un ticket puntual por id. Uso: /tkt show <id> en taso-bot."""
    ticket = await ticket_service.get_ticket(db, ticket_id=ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    return TicketAPIResponse(ok=True, data=TicketSchema.model_validate(ticket), count=1)


@router.patch("/{ticket_id}", response_model=TicketAPIResponse)
async def update_ticket_endpoint(
    ticket_id: int,
    body: TicketUpdateSchema,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Actualiza status y/o claimed_by de un ticket (botones Tomar/Resolver)."""
    ticket = await ticket_service.update_ticket(
        db, ticket_id=ticket_id, status=body.status, claimed_by=body.claimed_by,
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    return TicketAPIResponse(ok=True, data=TicketSchema.model_validate(ticket), count=1)
