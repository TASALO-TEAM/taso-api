"""Schemas de /liquidaciones (taso-bot M3a)."""

from datetime import datetime
from typing import List

from pydantic import BaseModel


class LiqItem(BaseModel):
    key: str
    long_usd: float
    short_usd: float
    total_usd: float


class LiqMeta(BaseModel):
    window: str
    by: str
    since: datetime
    coverage_from: datetime | None = None  # dato mas antiguo guardado (None si no hay)
    sources: List[str] = ["binance", "bybit", "okx"]


class LiqResponse(BaseModel):
    ok: bool = True
    data: List[LiqItem]
    meta: LiqMeta
