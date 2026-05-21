"""Year service: business logic for daily quotes, year progress, subscriptions.

Re-implements the core logic from the standalone year_manager.py
but operates on the database instead of flat JSON files.
Also includes a seed routine to load the initial quotes into DB.
"""

import json
import logging
import math
import os
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sql_func

from src.models.year_quote import YearQuote
from src.models.year_subscription import YearSubscription
from src.models.year_extra_flag import YearExtraFlag
from src.schemas.year import (
    QuoteContext, QuoteResponse, QuoteStats, YearProgressData,
    DailyQuoteResponse, QuoteListResponse, QuoteStatsResponse,
    YearStateResponse, SubscriptionResponse, SubscriptionListResponse,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

QUOTES_JSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..", "..", "year", "year", "year_quotes.json"
)


def _load_quotes_json(path: str = QUOTES_JSON_PATH) -> list[str]:
    """Load quotes from the flat JSON file."""
    target = os.path.normpath(path)
    if not os.path.exists(target):
        logger.warning("Quotes JSON not found at %s", target)
        return []
    with open(target, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        logger.warning("Quotes JSON is not a list at %s", target)
        return []
    return data


def _is_leap_year(year: int) -> bool:
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def _year_limit(year: int) -> int:
    return 366 if _is_leap_year(year) else 365


def _get_quote_context(index: int, current_year: int) -> QuoteContext:
    limit = _year_limit(current_year)
    if index < limit:
        return QuoteContext(current=index + 1, limit=limit, year=current_year, is_extra=False)
    next_year = current_year + 1
    return QuoteContext(
        current=index - limit + 1,
        limit=_year_limit(next_year),
        year=next_year,
        is_extra=True,
    )


async def seed_quotes_if_empty(db: AsyncSession) -> dict:
    """Import all quotes from year_quotes.json if the table is empty."""
    existing_count = await db.scalar(select(sql_func.count(YearQuote.id)))
    if existing_count and existing_count > 0:
        return {"seeded": False, "total": existing_count}
    quotes = _load_quotes_json()
    if not quotes:
        logger.warning("No quotes found in JSON to seed")
        return {"seeded": False, "total": 0}

    for text in quotes:
        db.add(YearQuote(quote_text=text))
    await db.commit()

    total = await db.scalar(select(sql_func.count(YearQuote.id)))
    logger.info("Seeded %d year quotes into DB", total)
    return {"seeded": True, "total": total}


# ---------------------------------------------------------------------------
# Quote CRUD
# ---------------------------------------------------------------------------

async def get_quote_stats(db: AsyncSession) -> QuoteStats:
    total = await db.scalar(select(sql_func.count(YearQuote.id))) or 0
    now = datetime.now()
    today = now.timetuple().tm_yday
    limit = _year_limit(now.year)
    current_index = (today - 1) % max(total, 1) if total > 0 else 0
    return QuoteStats(
        total=total,
        limit=limit,
        current_index=current_index,
        has_reached_limit=total >= limit,
        next_year_count=max(0, total - limit),
    )


async def get_daily_quote(db: AsyncSession) -> DailyQuoteResponse:
    total = await db.scalar(select(sql_func.count(YearQuote.id))) or 0
    now = datetime.now()
    if total == 0:
        ctx = QuoteContext(current=0, limit=_year_limit(now.year), year=now.year, is_extra=False)
        return DailyQuoteResponse(
            ok=True,
            quote="⏳ El tiempo vuela, pero tú eres el piloto.",
            index=-1,
            context=ctx,
        )
    day_of_year = now.timetuple().tm_yday
    index = (day_of_year - 1) % total
    result = await db.execute(select(YearQuote).order_by(YearQuote.id).offset(index).limit(1))
    row = result.scalar_one_or_none()
    quote_text = row.quote_text if row else "⏳ El tiempo vuela, pero tú eres el piloto."
    ctx = _get_quote_context(index, now.year)
    return DailyQuoteResponse(ok=True, quote=quote_text, index=index, context=ctx)


async def get_all_quotes(db: AsyncSession) -> QuoteListResponse:
    result = await db.execute(select(YearQuote).order_by(YearQuote.id))
    rows = result.scalars().all()
    return QuoteListResponse(
        ok=True,
        data=[QuoteResponse(id=r.id, quote_text=r.quote_text, created_at=r.created_at) for r in rows],
        count=len(rows),
    )


async def add_quote(db: AsyncSession, quote_text: str, target_year: Optional[int] = None) -> tuple[Optional[YearQuote], bool]:
    """Returns (quote_or_none, is_duplicate).

    Args:
        db: Database session
        quote_text: Quote text to add
        target_year: Optional year bucket (for placement planning; currently appends to end)
    """
    existing = (await db.execute(select(YearQuote.quote_text).where(YearQuote.quote_text == quote_text))).scalar_one_or_none()
    if existing:
        return None, True
    db.add(YearQuote(quote_text=quote_text))
    await db.commit()
    # Re-fetch via async SELECT
    result = await db.execute(select(YearQuote).where(YearQuote.quote_text == quote_text))
    new_row = result.scalar_one_or_none()
    return new_row, False


async def get_quote_by_id(db: AsyncSession, quote_id: int) -> Optional[YearQuote]:
    return (await db.execute(select(YearQuote).where(YearQuote.id == quote_id))).scalar_one_or_none()


async def delete_quote(db: AsyncSession, quote_id: int) -> bool:
    row = await get_quote_by_id(db, quote_id)
    if not row:
        return False
    await db.delete(row)
    await db.commit()
    logger.info("Deleted year quote id=%s", quote_id)
    return True


# ---------------------------------------------------------------------------
# Year Progress
# ---------------------------------------------------------------------------

async def get_year_progress() -> YearProgressData:
    now = datetime.now()
    start = datetime(now.year, 1, 1)
    end = datetime(now.year + 1, 1, 1)
    total_sec = (end - start).total_seconds()
    elapsed_sec = (now - start).total_seconds()
    return YearProgressData(
        year=now.year,
        percent=(elapsed_sec / total_sec) * 100,
        days_left=(end - now).days,
        date_str=now.strftime("%d/%m/%Y"),
    )


def generate_progress_bar(percent: float, length: int = 20) -> str:
    filled = int(length * percent // 100)
    return "▓" * filled + "░" * (length - filled)


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

async def get_all_subscriptions(db: AsyncSession) -> SubscriptionListResponse:
    result = await db.execute(select(YearSubscription).order_by(YearSubscription.id))
    rows = result.scalars().all()
    return SubscriptionListResponse(
        ok=True,
        data=[
            SubscriptionResponse(
                id=r.id, user_id=r.user_id, hour=r.hour,
                created_at=r.created_at, updated_at=r.updated_at,
            )
            for r in rows
        ],
        count=len(rows),
    )


async def set_subscription(db: AsyncSession, user_id: int, hour: int) -> YearSubscription:
    stmt = (
        select(YearSubscription).where(YearSubscription.user_id == user_id)
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        existing.hour = hour
    else:
        existing = YearSubscription(user_id=user_id, hour=hour)
        db.add(existing)
    await db.commit()
    await db.refresh(existing)
    return existing


async def delete_subscription(db: AsyncSession, user_id: int) -> bool:
    result = await db.execute(select(YearSubscription).where(YearSubscription.user_id == user_id))
    row = result.scalar_one_or_none()
    if not row:
        return False
    await db.delete(row)
    await db.commit()
    return True


async def get_enabled_subscriptions(db: AsyncSession) -> list[YearSubscription]:
    """Return all subscriptions (all registered ones are subscribed)."""
    result = await db.execute(select(YearSubscription))
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Extra Flag & New Year
# ---------------------------------------------------------------------------

async def is_new_year(db: AsyncSession, override_year: int | None = None) -> bool:
    """Return True if today is January 1 AND a greeting quote hasn't been added yet."""
    now = datetime.now()
    check_year = override_year or now.year
    if now.month != 1 or now.day != 1:
        return False
    greeting = f"🎉 Feliz año {check_year}!"
    result = await db.execute(
        select(YearQuote).where(YearQuote.quote_text == greeting).limit(1)
    )
    return result.scalar_one_or_none() is None


async def add_new_year_greeting(db: AsyncSession, override_year: int | None = None) -> YearQuote | None:
    """Add a 🎉 Feliz año {year}! greeting quote if today is Jan 1 and it doesn't exist."""
    now = datetime.now()
    add_year = override_year or now.year
    if now.month != 1 or now.day != 1:
        return None
    greeting = f"🎉 Feliz año {add_year}!"
    existing = (await db.execute(
        select(YearQuote).where(YearQuote.quote_text == greeting).limit(1)
    )).scalar_one_or_none()
    if existing:
        return existing
    db.add(YearQuote(quote_text=greeting))
    await db.commit()
    result = await db.execute(
        select(YearQuote).where(YearQuote.quote_text == greeting).limit(1)
    )
    row = result.scalar_one_or_none()
    if row:
        logger.info("✅ New year greeting added: %s", greeting)
    return row


async def get_or_create_extra_flag(db: AsyncSession, year: int) -> YearExtraFlag:
    """Return existing YearExtraFlag for year, or create one with asked=False."""
    result = await db.execute(select(YearExtraFlag).where(YearExtraFlag.year == year))
    flag = result.scalar_one_or_none()
    if flag:
        return flag
    flag = YearExtraFlag(year=year, asked=False)
    db.add(flag)
    await db.commit()
    await db.refresh(flag)
    return flag


async def set_extra_flag_asked(db: AsyncSession, year: int, asked: bool = True) -> YearExtraFlag:
    """Set the 'asked' flag for a given year. Creates record if needed."""
    flag = await get_or_create_extra_flag(db, year)
    flag.asked = asked
    await db.commit()
    await db.refresh(flag)
    return flag


# ---------------------------------------------------------------------------
# Extended daily quote (full context — for add-quote confirmation flow)
# ---------------------------------------------------------------------------


async def get_extended_daily_quote(db: AsyncSession) -> dict:
    """Return full year state + daily quote as a flat dict (for /y add confirmation)."""
    progress = get_year_progress()
    daily = await get_daily_quote(db)
    stats = await get_quote_stats(db)
    return {
        "ok": True,
        "progress": progress.model_dump(),
        "quote": daily.model_dump(),
        "stats": stats.model_dump(),
    }


# ---------------------------------------------------------------------------
# Legacy migration
# ---------------------------------------------------------------------------


async def migrate_legacy_subs(db: AsyncSession) -> dict:
    """Import subscriptions from the legacy JSON file if DB table is empty."""
    existing = (await db.execute(select(sql_func.count(YearSubscription.id)))).scalar() or 0
    if existing > 0:
        return {"migrated": False, "total": existing}

    legacy_path = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "year", "year", "year_subs.json")
    )
    if not os.path.exists(legacy_path):
        logger.warning("Legacy subs JSON not found at %s", legacy_path)
        return {"migrated": False, "total": 0}

    with open(legacy_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    migrated = 0
    for uid_str, data in raw.items():
        try:
            uid = int(uid_str)
            hour = data.get("hour", 6)
            db.add(YearSubscription(user_id=uid, hour=hour))
            migrated += 1
        except (ValueError, TypeError):
            logger.warning("Invalid sub entry: %s = %s", uid_str, data)

    await db.commit()
    logger.info("Migrated %d legacy year subscriptions from JSON", migrated)
    return {"migrated": True, "total": migrated}
