"""Historial diario de tasas: un precio por fecha de Cuba.

La app móvil necesita una serie liviana (un punto por día) en vez de las lecturas sueltas que se guardan cada
15 minutos en ``rate_snapshots``. Regla de negocio:

- Los días se agrupan por **fecha local de Cuba** (``America/Havana``, con su horario de verano), no por UTC.
- El precio de cada día es el de las **7:00 a. m. de Cuba** o, si no hay uno exacto, la lectura más cercana a esa hora
  *del mismo día local*.
- Los días sin ninguna lectura **no aparecen** (el cliente muestra «sin dato»; nunca se interpola).
- QvaPay: ``rate`` es el promedio de compra y venta (como en ``/tasas/qvapay``). El resto de fuentes usa ``sell_rate``
  (o ``buy_rate`` si no hay venta).
"""

from __future__ import annotations

import logging
import time as _time
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.rate_snapshot import RateSnapshot

logger = logging.getLogger(__name__)

CUBA_TZ = ZoneInfo("America/Havana")
DAILY_HOUR = 7

# Fuentes que se incluyen en el resumen para las tarjetas de la app.
SUMMARY_SOURCES = ("eltoque", "cadeca", "bcc", "qvapay")

# Una consulta de resumen recorre ~100 000 filas; se cachea poco tiempo en memoria del proceso.
CACHE_TTL_SECONDS = 300
_cache: dict[tuple, tuple[float, object]] = {}


def clear_cache() -> None:
    """Vacía el caché en memoria (lo usan los tests)."""
    _cache.clear()


def _cached(key: tuple):
    hit = _cache.get(key)
    if hit and _time.monotonic() - hit[0] < CACHE_TTL_SECONDS:
        return hit[1]
    return None


def snapshot_rate(source: str, buy, sell) -> float | None:
    """Precio de una lectura según la fuente; ``None`` si no hay un valor válido (> 0)."""
    buy_f = float(buy) if buy is not None else None
    sell_f = float(sell) if sell is not None else None
    if source == "qvapay" and buy_f is not None and sell_f is not None:
        value = (buy_f + sell_f) / 2
    else:
        value = sell_f if sell_f is not None else buy_f
    return value if value is not None and value > 0 else None


def reduce_daily(rows: Iterable[tuple[datetime, float]]) -> list[tuple[date, float]]:
    """Un precio por fecha de Cuba: la lectura más cercana a las 7:00 de ese día. Salida ordenada por fecha."""
    best: dict[date, tuple[float, float]] = {}
    for fetched_at, rate in rows:
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        local = fetched_at.astimezone(CUBA_TZ)
        day = local.date()
        target = datetime.combine(day, time(DAILY_HOUR), tzinfo=CUBA_TZ)
        # Se compara en UTC para no depender de cómo Python resta fechas con la misma zona.
        distance = abs((fetched_at.astimezone(timezone.utc) - target.astimezone(timezone.utc)).total_seconds())
        current = best.get(day)
        if current is None or distance < current[0]:
            best[day] = (distance, rate)
    return [(day, rate) for day, (_, rate) in sorted(best.items())]


def _window(days: int, now: datetime | None = None) -> tuple[datetime, date]:
    """Inicio de la consulta (UTC, con un día de margen) y primera fecha de Cuba que se devuelve."""
    now = now or datetime.now(timezone.utc)
    first_day = now.astimezone(CUBA_TZ).date() - timedelta(days=days - 1)
    return now - timedelta(days=days + 1), first_day


async def get_daily(
    session: AsyncSession, source: str, currency: str, days: int, now: datetime | None = None
) -> list[tuple[date, float]]:
    """Serie diaria de una fuente y moneda para los últimos ``days`` días de Cuba."""
    key = ("daily", source, currency, days)
    if now is None and (hit := _cached(key)) is not None:
        return hit  # type: ignore[return-value]
    cutoff, first_day = _window(days, now)
    stmt = (
        select(RateSnapshot.fetched_at, RateSnapshot.buy_rate, RateSnapshot.sell_rate)
        .where(
            RateSnapshot.source == source,
            RateSnapshot.currency == currency,
            RateSnapshot.fetched_at >= cutoff,
        )
        .order_by(RateSnapshot.fetched_at.asc())
    )
    try:
        result = await session.execute(stmt)
        rows = result.all()
    except Exception as exc:  # la app puede seguir sin historial
        logger.error("DB error en historial diario %s/%s: %s", source, currency, exc)
        return []
    readings = [
        (fetched_at, rate)
        for fetched_at, buy, sell in rows
        if (rate := snapshot_rate(source, buy, sell)) is not None
    ]
    points = [(d, r) for d, r in reduce_daily(readings) if d >= first_day]
    if now is None:
        _cache[key] = (_time.monotonic(), points)
    return points


async def get_summary(
    session: AsyncSession, days: int, now: datetime | None = None
) -> dict[str, dict[str, list[tuple[date, float]]]]:
    """Serie diaria de todas las fuentes y monedas: ``{fuente: {MONEDA: [(fecha, precio), ...]}}``."""
    key = ("summary", days)
    if now is None and (hit := _cached(key)) is not None:
        return hit  # type: ignore[return-value]
    cutoff, first_day = _window(days, now)
    stmt = (
        select(
            RateSnapshot.source,
            RateSnapshot.currency,
            RateSnapshot.fetched_at,
            RateSnapshot.buy_rate,
            RateSnapshot.sell_rate,
        )
        .where(RateSnapshot.source.in_(SUMMARY_SOURCES), RateSnapshot.fetched_at >= cutoff)
        .order_by(RateSnapshot.fetched_at.asc())
    )
    try:
        result = await session.execute(stmt)
        rows = result.all()
    except Exception as exc:
        logger.error("DB error en resumen de historial: %s", exc)
        return {}
    grouped: dict[tuple[str, str], list[tuple[datetime, float]]] = {}
    for source, currency, fetched_at, buy, sell in rows:
        # CUP no es una moneda de las fuentes de tasas (en QvaPay sí: es un método de pago).
        if currency == "CUP" and source != "qvapay":
            continue
        rate = snapshot_rate(source, buy, sell)
        if rate is not None:
            grouped.setdefault((source, currency), []).append((fetched_at, rate))
    data: dict[str, dict[str, list[tuple[date, float]]]] = {}
    for (source, currency), readings in grouped.items():
        points = [(d, r) for d, r in reduce_daily(readings) if d >= first_day]
        if points:
            data.setdefault(source, {})[currency] = points
    if now is None:
        _cache[key] = (_time.monotonic(), data)
    return data
