"""Pydantic schemas for local history endpoint."""

from pydantic import BaseModel
from datetime import date as DateType, datetime
from typing import List


class LocalHistorySnapshot(BaseModel):
    """Single snapshot from local history."""

    fetched_at: datetime
    usd_rate: float | None = None
    eur_rate: float | None = None
    mlc_rate: float | None = None

    class Config:
        from_attributes = True


class LocalHistoryResponse(BaseModel):
    """Response model for local history endpoint."""

    ok: bool
    data: List[LocalHistorySnapshot]
    count: int
    source: str = "local"


class DailyPoint(BaseModel):
    """Precio de un día (el de las 7:00 a. m. de Cuba o la lectura más cercana)."""

    date: DateType
    rate: float


class DailyHistoryResponse(BaseModel):
    """Serie diaria de una fuente y moneda. Los días sin lectura no aparecen."""

    ok: bool = True
    source: str
    currency: str
    tz: str = "America/Havana"
    days: int
    data: List[DailyPoint]


class SummaryHistoryResponse(BaseModel):
    """Serie diaria de todas las fuentes y monedas: ``data[fuente][MONEDA] = [{date, rate}]``."""

    ok: bool = True
    tz: str = "America/Havana"
    days: int
    data: dict[str, dict[str, List[DailyPoint]]]
