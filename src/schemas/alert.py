"""Pydantic schemas for price alert endpoints."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class PriceAlertSchema(BaseModel):
    """Schema de respuesta para una alerta de precio."""

    id: int
    user_id: int
    coin: str
    target_price: float
    price_at_creation: Optional[float] = None   # precio real al momento de crear
    condition: str   # "ABOVE" | "BELOW"
    status: str      # "ACTIVE" | "TRIGGERED"
    note: Optional[str] = None   # origen, ej: "S1 · Análisis 4h" (None si se creó manual)
    created_at: datetime
    updated_at: Optional[datetime] = None
    triggered_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AlertCreateSchema(BaseModel):
    """Schema para crear alertas de precio.

    Recibe el precio actual de la moneda en el momento de la creación
    para que el checker pueda detectar cruces reales y evitar falsos positivos.
    """

    user_id: int
    coin: str = Field(..., min_length=2, max_length=20)
    target_price: float = Field(..., gt=0)
    price_at_creation: float = Field(..., gt=0)   # precio real al momento de crear
    note: Optional[str] = Field(None, max_length=120)  # origen, ej: "S1 · Análisis 4h"

    @field_validator("coin")
    @classmethod
    def coin_upper(cls, v: str) -> str:
        return v.strip().upper()


class AlertDeleteSchema(BaseModel):
    """Schema para eliminar una alerta específica por id."""

    alert_id: int


class ActiveCoinsResponse(BaseModel):
    """Lista de coins que tienen al menos una alerta ACTIVE."""

    coins: List[str]
    count: int


class PriceAlertAPIResponse(BaseModel):
    """Wrapper genérico de respuesta para endpoints de alertas."""

    ok: bool
    data: Optional[object] = None
    error: Optional[dict] = None
    count: Optional[int] = None
