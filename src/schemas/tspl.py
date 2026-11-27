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


class TsplDigestPut(BaseModel):
    """Body de PUT /tspl/digest/latest (lo envía taso-bot al generar el digest)."""
    telegram_text: str = Field(..., min_length=1, max_length=4096)
    blog_markdown: str | None = Field(default=None, max_length=100_000)
    generated_at: datetime


class TsplDigestResponse(BaseModel):
    ok: bool = True
    telegram_text: str
    blog_markdown: str | None = None
    generated_at: datetime
    updated_at: datetime
