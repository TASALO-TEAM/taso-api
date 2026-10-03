"""Pydantic schemas para los mensajes de la app Android (AppMessage)."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

MessageFormat = Literal["telegram", "markdown"]


class AppMessageSchema(BaseModel):
    """Schema completo (uso admin)."""

    id: int
    title: str
    body: str
    format: str
    is_active: bool
    created_by: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppMessagePublicSchema(BaseModel):
    """Schema público: solo lo que necesita la app para mostrar el mensaje.

    No expone created_by (el user_id de Telegram del admin) a consumidores sin autenticación.
    """

    id: int
    title: str
    body: str
    format: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppMessageCreateSchema(BaseModel):
    """Crear un mensaje. El título es la primera línea; el límite del cuerpo es el de Telegram."""

    title: str = Field(..., min_length=1, max_length=120)
    body: str = Field(..., min_length=1, max_length=4096)
    format: MessageFormat = "telegram"
    created_by: Optional[int] = None


class AppMessageUpdateSchema(BaseModel):
    """Editar un mensaje. Todos los campos son opcionales."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    body: Optional[str] = Field(default=None, min_length=1, max_length=4096)
    format: Optional[MessageFormat] = None
    is_active: Optional[bool] = None


class AppMessageAPIResponse(BaseModel):
    """Wrapper genérico de respuesta (mismo formato que ads)."""

    ok: bool
    data: Optional[object] = None
    error: Optional[dict] = None
    count: Optional[int] = None
