"""Year service: business logic for daily quotes, year progress, subscriptions.

Redesigned with positional semantics:
  - quote.id   → position in ordered list (1-indexed, stable after reindex)
  - position 1 → "🎉 Feliz año {year}!" (always generated at query time, never stored)
  - positions 2+ → user quotes (stored in DB, managed by id)

Delete → reindex: if a slot is freed all following slots shift up by 1,
quotes keep their order but may now occupy a different calendar day.
"""

import json
import logging
import math
import os
import random
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select, func as sql_func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.year_quote import YearQuote
from src.models.year_subscription import YearSubscription
from src.models.year_extra_flag import YearExtraFlag
from src.schemas.year import (
    QuoteContext, QuoteResponse, QuoteStats, YearProgressData,
    DailyQuoteResponse, QuoteListResponse, QuoteStatsResponse,
    YearStateResponse, SubscriptionResponse, SubscriptionListResponse,
    AddQuoteResponse, EditQuoteRequest, EditQuoteResponse,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

QUOTES_JSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..", "..", "..", "year", "year_quotes.json"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    """Returns 365 or 366 depending on year type."""
    return 366 if _is_leap_year(year) else 365


# ---------------------------------------------------------------------------
# Core: ordered quote list
# ---------------------------------------------------------------------------


async def _list_quotes_ordered(db: AsyncSession) -> list[YearQuote]:
    """Return all quotes ordered by their id ASC."""
    result = await db.execute(select(YearQuote).order_by(YearQuote.id))
    return list(result.scalars().all())


async def _get_quote_by_seq(db: AsyncSession, seq: int) -> Optional[YearQuote]:
    """Return quote at 0-indexed position *seq* in the ordered list, or None.

    Raises ValueError if seq < 0.
    """
    if seq < 0:
        raise ValueError("seq must be >= 0")
    quotes = await _list_quotes_ordered(db)
    if seq >= len(quotes):
        return None
    return quotes[seq]


async def reindex_quotes(db: AsyncSession) -> int:
    """Reassign sequential ids to all quotes starting from 2 (1 = Feliz año slot).

    Returns number of rows updated.
    """
    quotes = await _list_quotes_ordered(db)
    count = 0
    for idx, quote in enumerate(quotes):
        new_id = idx + 2  # id=1 is Feliz año (never stored in DB)
        if quote.id != new_id:
            # Save current text; update id; commit
            old_text = quote.quote_text
            # SQLAlchemy can't update PK in DB in-place reliably;
            # delete + re-insert is the safe way.
            await db.delete(quote)
            db.add(YearQuote(id=new_id, quote_text=old_text))
            count += 1
    await db.commit()
    logger.info("Reindexed %d quotes (now ids start at 2)", count)
    return count


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------


def _get_quote_seq(index: int, target_year: int | None = None) -> QuoteContext:
    """Given a 0-based *index* into the user-quote list, return contextual info.

    Position 1 (id=1) = Feliz año — never in DB, handled in _get_quote_context.
    index=0 maps to slot position=2 (day 2), index=365 → position=366.

    If *target_year* is given, use it as the *reference year* instead of
    ``datetime.now().year``.  This is important when the quote list has already
    overflowed into the next year and the caller needs the *target-year* context
    rather than the in-progress year.
    """
    now = datetime.now()
    ref_year = target_year if target_year is not None else now.year
    ref_limit = _year_limit(ref_year)

    # index == 0 → second slot = day 2; index == 365 → day 366
    position_in_list = index + 1   # 1-based in user-quote list (starts at slot 2)
    day_of_year    = position_in_list + 1  # +1 because slot 1 = day 1 = Feliz año

    if day_of_year <= ref_limit:
        return QuoteContext(
            current=day_of_year,
            limit=ref_limit,
            year=ref_year,
            is_extra=False,
        )

    next_year   = ref_year + 1
    extra_limit = _year_limit(next_year)
    over        = day_of_year - ref_limit
    return QuoteContext(
        current=over + 1,
        limit=extra_limit,
        year=next_year,
        is_extra=True,
    )


def _get_quote_context_from_seq(index: int) -> QuoteContext:
    """Public-facing wrapper for _get_quote_seq (for use in routers)."""
    return _get_quote_seq(index)


def _get_quote_context(index: int, current_year: int) -> QuoteContext:
    """Deprecated – use _get_quote_seq instead. Kept for backward compat."""
    return _get_quote_seq(index)


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


async def seed_quotes_if_empty(db: AsyncSession) -> dict:
    """Import all quotes from year_quotes.json if the table is empty."""
    existing_count = await db.scalar(select(sql_func.count(YearQuote.id)))
    if existing_count and existing_count > 0:
        return {"seeded": False, "total": existing_count}
    quotes = _load_quotes_json()
    if not quotes:
        logger.warning("No quotes found in JSON to seed")
        return {"seeded": False, "total": 0}

    for idx, text in enumerate(quotes):
        db.add(YearQuote(id=idx + 2, quote_text=text))
    await db.commit()

    total = await db.scalar(select(sql_func.count(YearQuote.id)))
    logger.info("Seeded %d year quotes into DB (ids start at 2)", total)
    return {"seeded": True, "total": total}


# ---------------------------------------------------------------------------
# Quote stats
# ---------------------------------------------------------------------------


async def get_quote_stats(db: AsyncSession) -> QuoteStats:
    total = await db.scalar(select(sql_func.count(YearQuote.id))) or 0
    now = datetime.now()
    today = now.timetuple().tm_yday
    limit = _year_limit(now.year)
    # index into user-quote list (0-based): day 1 = Feliz año (not in list)
    user_idx = max(0, today - 2)
    # Wrap around only if we have actual quotes
    count = total
    current_index = user_idx % max(count, 1) if count > 0 else 0
    has_reached_limit = total >= limit
    next_year_count = max(0, total - limit)
    return QuoteStats(
        total=total,
        limit=limit,
        current_index=current_index,
        has_reached_limit=has_reached_limit,
        next_year_count=next_year_count,
    )


# ---------------------------------------------------------------------------
# Daily quote
# ---------------------------------------------------------------------------


async def get_daily_quote(db: AsyncSession) -> DailyQuoteResponse:
    """Return the quote for today.

    Day 1 → always "Feliz año {current_year}!" (not in DB, id=-1).
    Days 2+ → if slots_needed > total_quotes: random.choice(quotes);
              else deterministic slot mapping (index = day - 2).
    """
    now = datetime.now()
    day_of_year = now.timetuple().tm_yday  # 1-366
    quotes = await _list_quotes_ordered(db)
    total = len(quotes)

    # Day 1: Feliz año greeting, never stored in DB
    if day_of_year == 1:
        greeting = f"🎉 Feliz año {now.year}!"
        ctx = QuoteContext(current=1, limit=_year_limit(now.year),
                           year=now.year, is_extra=False)
        return DailyQuoteResponse(ok=True, quote=greeting, index=-1, context=ctx)

    # No quotes available
    if total == 0:
        placeholder = "⏳ El tiempo vuela, pero tú eres el piloto."
        ctx = QuoteContext(current=day_of_year, limit=_year_limit(now.year),
                           year=now.year, is_extra=False)
        return DailyQuoteResponse(ok=True, quote=placeholder, index=-1, context=ctx)

    # Slots needed to reach today (excluyendo día 1 = Feliz año)
    slots_needed = day_of_year - 2

    if slots_needed >= total:
        # Not enough quotes to fill all slots → pick random from available
        chosen = random.choice(quotes)
        ctx = _get_quote_seq(quotes.index(chosen))
        return DailyQuoteResponse(
            ok=True,
            quote=chosen.quote_text,
            index=chosen.id,
            context=ctx,
        )

    # Enough quotes → deterministic position
    idx = slots_needed
    row = quotes[idx]
    ctx = _get_quote_seq(idx)
    return DailyQuoteResponse(
        ok=True,
        quote=row.quote_text,
        index=row.id,
        context=ctx,
    )


# ---------------------------------------------------------------------------
# Quote CRUD
# ---------------------------------------------------------------------------


async def add_quote(
    db: AsyncSession,
    quote_text: str,
    target_year: Optional[int] = None,
) -> tuple[Optional[YearQuote], bool]:
    """Append a new user quote as the last position in the ordered list.

    Returns (quote_or_none, is_duplicate).
    Slot 1 (quote_id=1 = Feliz año) is auto-generated and protected —
    duplicate-text check ignores it as it's not stored.
    """
    existing = (
        await db.execute(
            select(YearQuote.quote_text).where(YearQuote.quote_text == quote_text)
        )
    ).scalar_one_or_none()
    if existing:
        return None, True

    # Fetch current last quote to compute next sequential id
    quotes = await _list_quotes_ordered(db)
    last_id = quotes[-1].id if quotes else 1

    new_quote = YearQuote(id=last_id + 1, quote_text=quote_text)
    db.add(new_quote)
    await db.commit()
    # Object has id assigned after commit; use it directly instead of re-fetch
    return new_quote, False


async def get_quote_by_id(db: AsyncSession, quote_id: int) -> Optional[YearQuote]:
    """Find a quote by its sequential position id. id=1 (Feliz año) is never stored → returns None."""
    if quote_id == 1:
        return None   # Feliz año slot, not stored in DB
    return (
        await db.execute(
            select(YearQuote).where(YearQuote.id == quote_id)
        )
    ).scalar_one_or_none()


async def edit_quote(db: AsyncSession, quote_id: int, new_text: str) -> Optional[YearQuote]:
    """Update text for a quote at position *quote_id*. quote_id=1 is locked.

    Returns the updated quote, or None if not found / id=1.
    """
    if quote_id == 1:
        return None
    row = await get_quote_by_id(db, quote_id)
    if not row:
        return None
    # Check text duplicate
    dup = (
        await db.execute(
            select(YearQuote).where(
                YearQuote.quote_text == new_text,
                YearQuote.id != quote_id,
            )
        )
    ).scalar_one_or_none()
    if dup:
        return None
    row.quote_text = new_text
    await db.commit()
    await db.refresh(row)
    return row


async def delete_quote(db: AsyncSession, quote_id: int) -> bool:
    """Delete a quote and reindex all remaining quotes (FR-4 requirement).

    Day 1 (quote_id=1) is locked -> returns False without deleting.
    After deletion all quotes following the removed slot shift up by one.
    reindex refreshes the sequential mapping.
    """
    if quote_id == 1:
        logger.warning("Blocked delete attempt on day 1 (Feliz año)")
        return False
    row = await get_quote_by_id(db, quote_id)
    if not row:
        return False
    await db.delete(row)
    await db.commit()
    logger.info("Deleted quote id=%s (%s)", quote_id, row.quote_text[:60])

    # Reindex remaining quotes so maps are contiguous again
    await reindex_quotes(db)
    return True


async def get_quote_by_seq(db: AsyncSession, seq: int) -> Optional[YearQuote]:
    """Get quote at 0-indexed *seq* position in the ordered list."""
    if seq < 0:
        return None
    quotes = await _list_quotes_ordered(db)
    if seq >= len(quotes):
        return None
    return quotes[seq]


async def get_all_quotes(db: AsyncSession) -> QuoteListResponse:
    """Return all user quotes ordered by id, starting from 2."""
    quotes = await _list_quotes_ordered(db)
    return QuoteListResponse(
        ok=True,
        data=[
            QuoteResponse(id=q.id, quote_text=q.quote_text, created_at=q.created_at)
            for q in quotes
        ],
        count=len(quotes),
    )


# ---------------------------------------------------------------------------
# Year progress
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
    stmt = select(YearSubscription).where(YearSubscription.user_id == user_id)
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
    result = await db.execute(
        select(YearSubscription).where(YearSubscription.user_id == user_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        return False
    await db.delete(row)
    await db.commit()
    return True


async def get_enabled_subscriptions(db: AsyncSession) -> list[YearSubscription]:
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
    existing = (
        await db.execute(
            select(YearQuote).where(YearQuote.quote_text == greeting).limit(1)
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    db.add(YearQuote(quote_text=greeting))
    await db.commit()
    result = await db.execute(
        select(YearQuote).where(YearQuote.quote_text == greeting).limit(1)
    )
    row = result.scalar_one_or_none()
    if row:
        logger.info("New year greeting added: %s", greeting)
    return row


async def get_or_create_extra_flag(db: AsyncSession, year: int) -> YearExtraFlag:
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
    flag = await get_or_create_extra_flag(db, year)
    flag.asked = asked
    await db.commit()
    await db.refresh(flag)
    return flag


# ---------------------------------------------------------------------------
# Extended daily quote (for add-quote confirmation flow)
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
    existing = (
        await db.execute(select(sql_func.count(YearSubscription.id)))
    ).scalar() or 0
    if existing > 0:
        return {"migrated": False, "total": existing}
    legacy_path = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "..", "..", "year", "year", "year_subs.json")
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
