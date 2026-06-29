"""Fuel price service.

Isolated service module for fetching, normalizing and persisting
informal fuel market prices from ElToque.

Designed to be completely independent of ``rates_service.py`` so it can
be evolved without risking any regression in the existing BCC/CADECA/ElToque
pipelines.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models.rate_snapshot import RateSnapshot
from src.scrapers.fuel import fetch_fuel


settings = get_settings()


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def _normalize_fuel_data(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert raw scraper output into the canonical snapshot shape.

    Returns a list of dicts with keys:

    - ``currency``
    - ``buy_rate``
    - ``sell_rate``

    This shape matches the one expected by ``RateSnapshot`` for ``source="fuel"``.
    """
    result: list[dict[str, Any]] = []
    for name, info in data.items():
        if not isinstance(info, dict):
            continue

        range_min = info.get("range_min")
        range_max = info.get("range_max")

        if range_min is None and range_max is None:
            continue

        buy = float(range_min) if range_min is not None else None
        sell = float(range_max) if range_max is not None else (buy if buy is not None else None)

        result.append(
            {
                "currency": name,
                "buy_rate": buy,
                "sell_rate": sell,
                "subtype": info.get("subtype"),
                "unit": info.get("unit"),
                "change_pct": info.get("change_pct"),
                "change_direction": info.get("change_direction"),
            }
        )
    return result


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

async def _get_latest_snapshot(db: AsyncSession, currency: str | None = None) -> RateSnapshot | None:
    stmt = (
        select(RateSnapshot)
        .where(RateSnapshot.source == "fuel")
        .order_by(RateSnapshot.fetched_at.desc())
        .limit(1 if currency is None else 5)  # small batch when currency is unknown
    )
    if currency:
        stmt = stmt.where(RateSnapshot.currency == currency)

    result = await db.execute(stmt)
    rows = result.scalars().unique().all()
    return rows[0] if rows else None


async def _get_previous_snapshot(db: AsyncSession, currency: str) -> RateSnapshot | None:
    """Return the most recent snapshot before the latest one for ``currency``."""
    latest = await _get_latest_snapshot(db, currency=currency)
    if latest is None:
        return None

    stmt = (
        select(RateSnapshot)
        .where(
            RateSnapshot.source == "fuel",
            RateSnapshot.currency == currency,
            RateSnapshot.id != latest.id,
        )
        .order_by(RateSnapshot.fetched_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    rows = result.scalars().unique().all()
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Core public API
# ---------------------------------------------------------------------------

async def fetch_and_save_fuel(db: AsyncSession) -> dict[str, dict[str, Any]] | None:
    """Fetch fresh fuel data, persist it and return the normalized payload.

    Returns ``None`` if the scraper fails or the normalized payload is empty.
    """
    raw = await fetch_fuel()
    if not raw:
        return None

    normalized = _normalize_fuel_data(raw)
    if not normalized:
        return None

    now = datetime.now(timezone.utc)

    for item in normalized:
        snapshot = RateSnapshot(
            source="fuel",
            currency=item["currency"],
            buy_rate=item.get("buy_rate"),
            sell_rate=item.get("sell_rate"),
            fetched_at=now,
        )
        # Attach extra fuel-specific metadata on the model via JSON if needed.
        # For now we rely on the currency key and buy/sell to represent state.
        db.add(snapshot)

    await db.commit()
    return raw


async def get_fuel_rates(db: AsyncSession, max_age_minutes: int = 60) -> tuple[dict[str, Any], datetime]:
    """Return the latest fuel rates ready for API response.

    The return value is a ``(rates, updated_at)`` tuple where ``rates`` is a dict::

        {
            "B-94": {"rate": 3200.0, "buy": 3200.0, "sell": 4710.0, ...},
            ...
        }

    ``updated_at`` is the ``fetched_at`` of the latest snapshot.
    """
    now = datetime.now(timezone.utc)
    latest = await _get_latest_snapshot(db)

    if latest is None or _is_stale(latest.fetched_at, now, max_age_minutes):
        # Lazy refresh on cache miss / stale data
        fresh = await fetch_and_save_fuel(db)
        if fresh is None:
            # Fallback to whatever we have (if anything)
            latest = await _get_latest_snapshot(db)
            if latest is None:
                return {}, now
        else:
            latest = await _get_latest_snapshot(db)

    if latest is None:
        return {}, now

    # Build response payload from recent fuel snapshots
    stmt = (
        select(RateSnapshot)
        .where(RateSnapshot.source == "fuel")
        .order_by(RateSnapshot.fetched_at.desc())
        .limit(20)
    )
    result = await db.execute(stmt)
    rows = result.scalars().unique().all()

    rates: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    for row in rows:
        if row.currency in seen:
            continue
        seen.add(row.currency)

        prev = await _get_previous_snapshot(db, row.currency)
        prev_rate = prev.sell_rate if prev else None
        current_rate = row.sell_rate if row.sell_rate is not None else row.buy_rate

        change = _compute_change(current_rate, prev_rate)

        rates[row.currency] = {
            "rate": current_rate,
            "buy": row.buy_rate,
            "sell": row.sell_rate,
            "change": change,
            "prev_rate": prev_rate,
            "subtype": getattr(row, "subtype", None),
            "unit": getattr(row, "unit", None),
            "change_pct": getattr(row, "change_pct", None),
            "change_direction": getattr(row, "change_direction", None),
        }

    return rates, latest.fetched_at


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_stale(fetched_at: datetime, now: datetime, max_age_minutes: int) -> bool:
    delta = now - fetched_at
    return delta.total_seconds() > max_age_minutes * 60


def _compute_change(current: float | None, previous: float | None) -> str:
    if current is None or previous is None:
        return "neutral"
    if current > previous:
        return "up"
    if current < previous:
        return "down"
    return "neutral"
