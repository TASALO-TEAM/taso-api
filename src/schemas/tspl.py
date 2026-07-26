"""Pydantic schemas for /tspl/subscriptions/* endpoints."""

from datetime import datetime
from pydantic import BaseModel, Field


class TsplSubscriptionCreate(BaseModel):
    """Request body for POST /tspl/subscriptions/me/{user_id}."""
    user_id: int
    hour: int = Field(..., ge=0, le=23)


class TsplSubscriptionResponse(BaseModel):
    ok: bool = True
    id: int
    user_id: int
    hour: int
    created_at: datetime


class TsplSubscriptionListResponse(BaseModel):
    ok: bool = True
    data: list[TsplSubscriptionResponse]
    count: int
