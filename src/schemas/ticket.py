"""Pydantic schemas for the tickets (user→admin contact) system."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

TICKET_KINDS = {"bug", "promo"}
# "approved"/"rejected" son exclusivos de tickets kind="promo" (ver
# docs/plans/2026-07-08-ms-directo-y-tkt-mejoras.md, Parte 4): un anuncio se
# aprueba o rechaza directamente en vez de pasar por in_progress/resolved.
TICKET_STATUSES = {"open", "in_progress", "resolved", "closed", "approved", "rejected"}


class TicketSchema(BaseModel):
    """Schema completo de un ticket (uso admin)."""

    id: int
    user_id: int
    username: Optional[str] = None
    kind: str
    message: str
    status: str
    claimed_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    stars_paid: bool = False

    model_config = ConfigDict(from_attributes=True)


class TicketCreateSchema(BaseModel):
    """Schema para crear un ticket nuevo. Lo envía taso-bot en nombre del usuario."""

    user_id: int
    username: Optional[str] = Field(None, max_length=100)
    kind: str
    message: str = Field(..., min_length=3, max_length=1000)

    @field_validator("kind")
    @classmethod
    def kind_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in TICKET_KINDS:
            raise ValueError(f"kind debe ser uno de {TICKET_KINDS}")
        return v


class TicketUpdateSchema(BaseModel):
    """Schema para editar status/claimed_by de un ticket existente."""

    status: Optional[str] = None
    claimed_by: Optional[int] = None

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in TICKET_STATUSES:
            raise ValueError(f"status debe ser uno de {TICKET_STATUSES}")
        return v


class TicketAPIResponse(BaseModel):
    """Wrapper genérico de respuesta para endpoints de tickets."""

    ok: bool
    data: Optional[object] = None
    error: Optional[dict] = None
    count: Optional[int] = None
