"""Pydantic schemas for local history endpoint."""

from pydantic import BaseModel
from datetime import datetime
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
