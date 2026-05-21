"""Router for /year/* endpoints."""

import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.middleware.auth import require_auth
from src.services import year_service
from src.models.year_subscription import YearSubscription
from src.schemas.year import (
    QuoteCreate,
    QuoteListResponse,
    QuoteStatsResponse,
    DailyQuoteResponse,
    YearStateResponse,
    SubscriptionCreate,
    SubscriptionResponse,
    SubscriptionListResponse,
    AddQuoteResponse,
)

logger = logging.getLogger(__name__)

# Public router for quote-reading endpoints
router = APIRouter(tags=["Year"])

# Admin router for write operations
admin_router = APIRouter(
    dependencies=[Depends(require_auth)],
)


# ── Quotes (public read) ──────────────────────────────────────────────────


@router.get("/quotes/today", response_model=DailyQuoteResponse)
async def get_today_quote(db: AsyncSession = Depends(get_db)):
    return await year_service.get_daily_quote(db)


@router.get("/quotes", response_model=QuoteListResponse)
async def list_quotes(db: AsyncSession = Depends(get_db)):
    return await year_service.get_all_quotes(db)


@router.get("/quotes/stats", response_model=QuoteStatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    stats = await year_service.get_quote_stats(db)
    return QuoteStatsResponse(data=stats)


@router.get("/state", response_model=YearStateResponse)
async def get_year_state(db: AsyncSession = Depends(get_db)):
    progress = await year_service.get_year_progress()
    quote_resp = await year_service.get_daily_quote(db)
    stats = await year_service.get_quote_stats(db)
    return YearStateResponse(
        ok=True,
        progress=progress.model_dump(),
        quote=quote_resp.model_dump(),
        stats=stats,
    )


# ── Subscriptions (public, user-facing) ──────────────────────────────────


@router.get("/subscriptions/me/{user_id}", response_model=SubscriptionResponse)
async def get_my_subscription(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(YearSubscription).where(YearSubscription.user_id == user_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription found for this user")
    return SubscriptionResponse(
        id=sub.id, user_id=sub.user_id, hour=sub.hour,
        created_at=sub.created_at, updated_at=sub.updated_at,
    )


@router.get("/subscriptions", response_model=SubscriptionListResponse)
async def list_all_subscriptions(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    return await year_service.get_all_subscriptions(db)


@admin_router.post("/subscriptions", response_model=SubscriptionResponse)
async def admin_set_subscription(body: SubscriptionCreate, db: AsyncSession = Depends(get_db)):
    sub = await year_service.set_subscription(db, body.user_id, body.hour)
    return SubscriptionResponse(
        id=sub.id, user_id=sub.user_id, hour=sub.hour,
        created_at=sub.created_at, updated_at=sub.updated_at,
    )


@admin_router.delete("/subscriptions/{user_id}")
async def admin_delete_subscription(user_id: int, db: AsyncSession = Depends(get_db)):
    ok = await year_service.delete_subscription(db, user_id)
    return {"ok": ok, "deleted": ok, "user_id": user_id}


# ── Extra Flag ───────────────────────────────────────────────────────────


@router.get("/extra-flag/{year}", response_model=dict)
async def get_extra_flag(year: int, db: AsyncSession = Depends(get_db)):
    """Get the extra-flag for a given year (creates if missing)."""
    flag = await year_service.get_or_create_extra_flag(db, year)
    return {"ok": True, "year": flag.year, "asked": flag.asked}


@admin_router.post("/extra-flag/{year}")
async def admin_set_extra_flag(year: int, asked: bool = True, db: AsyncSession = Depends(get_db)):
    """Set the 'asked' flag for a given year."""
    flag = await year_service.set_extra_flag_asked(db, year, asked)
    return {"ok": True, "year": flag.year, "asked": flag.asked}


# ── Quotes admin (write) ──────────────────────────────────────────────────


@admin_router.post("/quotes", response_model=AddQuoteResponse)
async def admin_add_quote(body: QuoteCreate, db: AsyncSession = Depends(get_db)):
    row, is_dup = await year_service.add_quote(db, body.quote_text, target_year=body.target_year)
    if is_dup:
        raise HTTPException(status_code=409, detail="Quote already exists")
    stats = await year_service.get_quote_stats(db)
    now = datetime.now()
    ctx = year_service._get_quote_context(stats.current_index, now.year)
    return AddQuoteResponse(
        ok=True,
        success=True,
        is_duplicate=False,
        index=stats.current_index,
        context=ctx,
    )


@admin_router.delete("/quotes/{quote_id}")
async def admin_delete_quote(quote_id: int, db: AsyncSession = Depends(get_db)):
    ok = await year_service.delete_quote(db, quote_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Quote not found")
    return {"ok": True, "deleted_id": quote_id}

