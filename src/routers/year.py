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
    EditQuoteRequest,
    EditQuoteResponse,
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


@admin_router.get("/quotes/{quote_id}")
async def admin_get_quote(quote_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single quote by its sequential position id (quote_id=1 is Feliz año)."""
    if quote_id == 1:
        return {
            "ok": True,
            "id": 1,
            "quote_text": "🎉 Feliz año {year}!".replace("{year}", str(datetime.now().year)),
            "created_at": None,
            "is_greeting": True,
        }
    row = await year_service.get_quote_by_id(db, quote_id)
    if not row:
        raise HTTPException(status_code=404, detail="Quote not found")
    return {
        "ok": True,
        "id": row.id,
        "quote_text": row.quote_text,
        "created_at": row.created_at,
        "is_greeting": False,
    }


@admin_router.post("/quotes", response_model=AddQuoteResponse)
async def admin_add_quote(body: QuoteCreate, db: AsyncSession = Depends(get_db)):
    row, is_dup = await year_service.add_quote(db, body.quote_text, target_year=body.target_year)
    if is_dup:
        raise HTTPException(status_code=409, detail="Quote already exists")
    now = datetime.now()
    # Use the actual quote position (row.id) to compute context
    # row.id is the sequential position; id=1 = Feliz año (never stored),
    # ids 2+ are user quotes → 0-based index = row.id - 2
    quote_index = row.id - 2
    # Determine which year the newly added quote lands in.
    # Prefer explicit target_year, otherwise: current in-progress year unless
    # all slots of the current year are already filled (overflow → next year).
    total = await year_service.get_quote_stats(db)
    ref_year = body.target_year if body.target_year is not None else (
        now.year + 1 if total.has_reached_limit else now.year
    )
    ctx = year_service._get_quote_seq(quote_index, target_year=ref_year)
    return AddQuoteResponse(
        ok=True,
        success=True,
        is_duplicate=False,
        index=quote_index,
        context=ctx,
        quote_id=row.id,
    )


@admin_router.put("/quotes/{quote_id}", response_model=EditQuoteResponse)
async def admin_edit_quote(quote_id: int, body: EditQuoteRequest, db: AsyncSession = Depends(get_db)):
    row = await year_service.edit_quote(db, quote_id, body.quote_text)
    if not row:
        if quote_id == 1:
            raise HTTPException(status_code=403, detail="Day 1 (Feliz año) is locked and cannot be edited")
        raise HTTPException(status_code=404, detail="Quote not found or text already exists")
    return EditQuoteResponse(ok=True, id=row.id, quote_text=row.quote_text, created_at=row.created_at)


@admin_router.delete("/quotes/{quote_id}")
async def admin_delete_quote(quote_id: int, db: AsyncSession = Depends(get_db)):
    ok = await year_service.delete_quote(db, quote_id)
    if not ok:
        if quote_id == 1:
            raise HTTPException(status_code=403, detail="Day 1 (Feliz año) is locked and cannot be deleted")
        raise HTTPException(status_code=404, detail="Quote not found")
    return {"ok": True, "deleted_id": quote_id, "reindexed": True}

