"""Pydantic schemas for /year/* endpoints."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class QuoteCreate(BaseModel):
    """Request body for POST /year/quotes (add a new quote)."""
    quote_text: str = Field(..., min_length=5, description="Quote text, minimum 5 chars")
    target_year: Optional[int] = Field(None, description="Target year for the quote position (current or next)")


class QuoteResponse(BaseModel):
    """Single quote in response."""
    id: int
    quote_text: str
    created_at: datetime


class QuoteListResponse(BaseModel):
    """List of quotes with pagination or stats info."""
    ok: bool = True
    data: list[QuoteResponse]
    count: int


class QuoteStats(BaseModel):
    """Statistics about quotes collection."""
    total: int
    limit: int       # 365 or 366
    current_index: int
    has_reached_limit: bool
    next_year_count: int


class QuoteStatsResponse(BaseModel):
    ok: bool = True
    data: QuoteStats


class YearProgressData(BaseModel):
    year: int
    percent: float
    days_left: int
    date_str: str


class QuoteContext(BaseModel):
    current: int
    limit: int
    year: int
    is_extra: bool


class DailyQuoteResponse(BaseModel):
    ok: bool = True
    quote: str
    index: int
    context: QuoteContext


class YearStateResponse(BaseModel):
    """Full year state: progress + daily quote."""
    ok: bool = True
    progress: dict
    quote: dict               # DailyQuoteResponse as dict
    stats: QuoteStats


class SubscriptionCreate(BaseModel):
    user_id: int
    hour: int = Field(..., ge=0, le=23)


class SubscriptionResponse(BaseModel):
    id: int
    user_id: int
    hour: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class SubscriptionListResponse(BaseModel):
    ok: bool = True
    data: list[SubscriptionResponse]
    count: int


class EditQuoteRequest(BaseModel):
    """Request body for PUT /year/quotes/{id} (edit a quote)."""
    quote_text: str = Field(..., min_length=5, description="New quote text, minimum 5 chars")


class EditQuoteResponse(BaseModel):
    ok: bool = True
    id: int
    quote_text: str
    created_at: datetime


class AddQuoteResponse(BaseModel):
    ok: bool = True
    success: bool
    is_duplicate: bool
    index: int
    context: QuoteContext
