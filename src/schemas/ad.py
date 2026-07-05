"""Pydantic schemas for the ads (announcements) system."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class AdSchema(BaseModel):
    """Schema completo de un anuncio (uso admin)."""

    id: int
    text: str
    is_active: bool
    is_sponsored: bool
    weight: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AdPublicSchema(BaseModel):
    """Schema público — solo lo necesario para renderizar y elegir el anuncio.

    No expone created_by ni timestamps a consumidores externos (taso-app,
    taso-ext) que consultan los endpoints sin autenticación. 'weight' sí se
    expone porque no es sensible y permite que cualquier consumidor replique
    la selección ponderada localmente (ej. el bot cachea /active y elige
    ponderado en memoria en vez de llamar a /random en cada mensaje).
    """

    id: int
    text: str
    is_sponsored: bool
    weight: int

    model_config = ConfigDict(from_attributes=True)


class AdCreateSchema(BaseModel):
    """Schema para crear un anuncio nuevo."""

    text: str = Field(..., min_length=1, max_length=300)
    is_sponsored: bool = False
    weight: int = Field(default=1, ge=1, le=100)
    created_by: Optional[int] = None

class AdUpdateSchema(BaseModel):
    """Schema para editar un anuncio existente. Todos los campos son opcionales."""

    text: Optional[str] = Field(default=None, min_length=1, max_length=300)
    is_active: Optional[bool] = None
    is_sponsored: Optional[bool] = None
    weight: Optional[int] = Field(default=None, ge=1, le=100)


class AdAPIResponse(BaseModel):
    """Wrapper genérico de respuesta para endpoints de ads."""

    ok: bool
    data: Optional[object] = None
    error: Optional[dict] = None
    count: Optional[int] = None
