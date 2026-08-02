"""Poda de tasas históricas — retención de 1 año.

Ver docs/plans/2026-08-01-comando-db-gestion-retencion-tasas.md. A
diferencia del plan viejo (2026-04-27-snapshot-cleanup-retention-plan.md,
nunca implementado), esto es borrado simple sin agregación: las gráficas
de análisis para las que se pensó ese histórico ya no son de interés.

No toca CubanomicRate (1 fila/día, no es problema de espacio).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TypedDict

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models.rate_snapshot import RateSnapshot
from src.models.rates import HistorySnapshot

logger = logging.getLogger(__name__)


class PruneResult(TypedDict):
    rate_snapshots_deleted: int
    history_snapshots_deleted: int
    cutoff_date: str
    days: int


async def prune_old_rates(db: AsyncSession, days: int | None = None) -> PruneResult:
    """Borra RateSnapshot y HistorySnapshot más viejos que `days`.

    Args:
        db: sesión async
        days: umbral de retención; por defecto Settings.rates_retention_days (365)

    Returns:
        PruneResult con conteos borrados y el cutoff usado.
    """
    if days is None:
        days = get_settings().rates_retention_days

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    rate_stmt = delete(RateSnapshot).where(RateSnapshot.fetched_at < cutoff)
    rate_result = await db.execute(rate_stmt)

    history_stmt = delete(HistorySnapshot).where(HistorySnapshot.fetched_at < cutoff)
    history_result = await db.execute(history_stmt)

    await db.commit()

    rate_deleted = rate_result.rowcount or 0
    history_deleted = history_result.rowcount or 0

    logger.info(
        "🧹 Poda de tasas (>%d días): %d rate_snapshots, %d history_snapshots borrados (cutoff=%s)",
        days, rate_deleted, history_deleted, cutoff.isoformat(),
    )

    return PruneResult(
        rate_snapshots_deleted=rate_deleted,
        history_snapshots_deleted=history_deleted,
        cutoff_date=cutoff.isoformat(),
        days=days,
    )
