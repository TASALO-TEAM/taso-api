"""Fuel price service.

Servicio aislado para precios de combustible del mercado informal (ElToque).
Completamente independiente de rates_service.py.

Estrategia de caché:
  - Los datos del scraper (subtype, unit, change_pct, change_direction) se guardan
    en memoria en _fuel_cache por hasta max_age_minutes.
  - Los precios numéricos (buy_rate, sell_rate) también se persisten en RateSnapshot
    para tener historial, pero los metadatos vienen siempre del scraper fresco.
  - Si el scraper falla, se devuelven los últimos datos de la caché en memoria,
    y como último fallback los precios numéricos de la DB.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.rate_snapshot import RateSnapshot
from src.scrapers.fuel import fetch_fuel

logger = logging.getLogger(__name__)

# ── Caché en memoria ─────────────────────────────────────────────────────────
# Almacena (rates_dict, fetched_at) entre requests para no scrapear en cada llamada
_fuel_cache: dict[str, Any] = {
    "rates": {},
    "fetched_at": None,
}


def _is_stale(fetched_at: Optional[datetime], now: datetime, max_age_minutes: int) -> bool:
    if fetched_at is None:
        return True
    delta = now - fetched_at
    return delta.total_seconds() > max_age_minutes * 60


# ── Normalización ─────────────────────────────────────────────────────────────

# Subtypes conocidos por clave normalizada (fallback si el scraper no los trae)
_SUBTYPES = {
    "B-94": "Especial",
    "B-90": "Regular",
    "B-83": "Motor",
    "Petroleo": "Diésel",
    "Gas_LP": "Balón",
}

_DISPLAY_NAMES = {
    "B-94": "B-94",
    "B-90": "B-90",
    "B-83": "B-83",
    "Petroleo": "Petróleo",
    "Gas_LP": "Gas LP",
}

_UNITS = {
    "Gas_LP": "CUP/balón",
}

_FUEL_ORDER = ["B-94", "B-90", "B-83", "Petroleo", "Gas_LP"]


def _normalize_fuel_rates(raw: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Convierte la salida del scraper al formato final para el endpoint y el bot."""
    result: dict[str, dict[str, Any]] = {}
    for key in _FUEL_ORDER:
        info = raw.get(key)
        if not info:
            continue

        range_min = info.get("range_min")
        range_max = info.get("range_max")
        primary = info.get("primary_value")

        if range_min is None and range_max is None and primary is None:
            continue

        buy = float(range_min) if range_min is not None else None
        sell = float(range_max) if range_max is not None else buy
        rate = float(primary) if primary is not None else sell

        # change vs snapshot anterior en DB
        change = "neutral"
        prev_rate = info.get("prev_median")

        result[key] = {
            "rate": rate,
            "buy": buy,
            "sell": sell,
            "change": change,
            "prev_rate": prev_rate,
            "subtype": info.get("subtype") or _SUBTYPES.get(key),
            "unit": info.get("unit") or _UNITS.get(key, "CUP/L"),
            "change_pct": info.get("change_pct"),
            "change_direction": info.get("change_direction", "neutral"),
            "display_name": _DISPLAY_NAMES.get(key, key),
        }

    return result


# ── Persistencia ──────────────────────────────────────────────────────────────

async def _save_to_db(db: AsyncSession, rates: dict[str, dict[str, Any]]) -> None:
    """Persiste los precios numéricos en rate_snapshots para historial."""
    now = datetime.now(timezone.utc)
    for key, info in rates.items():
        snapshot = RateSnapshot(
            source="fuel",
            currency=key,
            buy_rate=info.get("buy"),
            sell_rate=info.get("sell"),
            fetched_at=now,
        )
        db.add(snapshot)
    try:
        await db.commit()
        logger.info("💾 [fuel] %d snapshots guardados en DB", len(rates))
    except Exception as e:
        logger.error("❌ [fuel] Error guardando snapshots: %s", e)
        await db.rollback()


async def _enrich_with_prev_rate(db: AsyncSession, rates: dict[str, dict[str, Any]]) -> None:
    """Añade prev_rate y change comparando con el snapshot anterior en DB."""
    for key, info in rates.items():
        try:
            stmt = (
                select(RateSnapshot)
                .where(RateSnapshot.source == "fuel", RateSnapshot.currency == key)
                .order_by(RateSnapshot.fetched_at.desc())
                .offset(1)
                .limit(1)
            )
            result = await db.execute(stmt)
            prev = result.scalars().first()
            if prev and prev.sell_rate is not None:
                prev_rate = float(prev.sell_rate)
                current = info.get("sell") or info.get("buy")
                info["prev_rate"] = prev_rate
                if current is not None:
                    if current > prev_rate:
                        info["change"] = "up"
                    elif current < prev_rate:
                        info["change"] = "down"
        except Exception:
            pass  # No crítico


# ── API pública ───────────────────────────────────────────────────────────────

async def get_fuel_rates(
    db: AsyncSession,
    max_age_minutes: int = 60,
) -> tuple[dict[str, Any], datetime]:
    """Devuelve los precios de combustible listos para el endpoint.

    Returns:
        (rates_dict, updated_at)
    """
    global _fuel_cache
    now = datetime.now(timezone.utc)

    # Usar caché en memoria si está fresca
    if not _is_stale(_fuel_cache["fetched_at"], now, max_age_minutes) and _fuel_cache["rates"]:
        logger.debug("♻️ [fuel] Sirviendo desde caché en memoria (edad=%s)",
                     now - _fuel_cache["fetched_at"])
        return _fuel_cache["rates"], _fuel_cache["fetched_at"]

    # Scrapear datos frescos
    logger.info("⛽ [fuel] Caché stale o vacía, iniciando scraping...")
    raw = await fetch_fuel()

    if raw:
        rates = _normalize_fuel_rates(raw)
        if rates:
            await _enrich_with_prev_rate(db, rates)
            await _save_to_db(db, rates)
            _fuel_cache["rates"] = rates
            _fuel_cache["fetched_at"] = now
            logger.info("✅ [fuel] %d tipos de combustible obtenidos", len(rates))
            return rates, now

    # Fallback 1: caché en memoria (aunque stale)
    if _fuel_cache["rates"]:
        logger.warning("⚠️ [fuel] Scraper falló, usando caché stale de %s", _fuel_cache["fetched_at"])
        return _fuel_cache["rates"], _fuel_cache["fetched_at"]

    # Fallback 2: últimos precios numéricos de la DB (sin metadatos ricos)
    logger.warning("⚠️ [fuel] Intentando fallback de DB...")
    db_rates = await _get_from_db(db)
    if db_rates:
        return db_rates, now

    logger.error("❌ [fuel] Sin datos de ninguna fuente")
    return {}, now


async def _get_from_db(db: AsyncSession) -> dict[str, dict[str, Any]]:
    """Fallback: lee los últimos precios numéricos de la DB."""
    try:
        stmt = (
            select(RateSnapshot)
            .where(RateSnapshot.source == "fuel")
            .order_by(RateSnapshot.fetched_at.desc())
            .limit(20)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        rates: dict[str, dict[str, Any]] = {}
        seen: set[str] = set()
        for row in rows:
            if row.currency in seen:
                continue
            seen.add(row.currency)
            sell = float(row.sell_rate) if row.sell_rate else None
            buy = float(row.buy_rate) if row.buy_rate else None
            rates[row.currency] = {
                "rate": sell or buy,
                "buy": buy,
                "sell": sell,
                "change": "neutral",
                "prev_rate": None,
                "subtype": _SUBTYPES.get(row.currency),
                "unit": _UNITS.get(row.currency, "CUP/L"),
                "change_pct": None,
                "change_direction": "neutral",
                "display_name": _DISPLAY_NAMES.get(row.currency, row.currency),
            }
        return rates
    except Exception as e:
        logger.error("❌ [fuel] Error en fallback DB: %s", e)
        return {}
