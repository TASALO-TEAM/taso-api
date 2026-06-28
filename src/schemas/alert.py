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
    condition: str   # "ABOVE" | "BELOW"
    status: str      # "ACTIVE" | "TRIGGERED"
    created_at: datetime
    updated_at: Optional[datetime] = None
    triggered_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AlertCreateSchema(BaseModel):
    """Schema para crear una alerta de precio.

    Siempre crea dos alertas (ABOVE + BELOW) para el par coin/price.
    """

    user_id: int
    coin: str = Field(..., min_length=2, max_length=20)
    target_price: float = Field(..., gt=0)

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
