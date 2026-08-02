"""Tests para retention_service.prune_old_rates()."""

import pytest
from datetime import datetime, timedelta, timezone

from src.models.rate_snapshot import RateSnapshot
from src.models.rates import HistorySnapshot
from src.services.retention_service import prune_old_rates


def _make_rate_snapshot(fetched_at: datetime) -> RateSnapshot:
    return RateSnapshot(
        source="eltoque",
        currency="USD",
        sell_rate=350.0,
        fetched_at=fetched_at,
    )


def _make_history_snapshot(fetched_at: datetime) -> HistorySnapshot:
    return HistorySnapshot(eltoque_usd=350.0, fetched_at=fetched_at)


@pytest.mark.asyncio
async def test_prune_deletes_only_rows_older_than_cutoff(db_session):
    """Filas más viejas que `days` se borran; las recientes se conservan."""
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=400)
    recent = now - timedelta(days=10)

    db_session.add(_make_rate_snapshot(old))
    db_session.add(_make_rate_snapshot(recent))
    db_session.add(_make_history_snapshot(old))
    db_session.add(_make_history_snapshot(recent))
    await db_session.commit()

    result = await prune_old_rates(db_session, days=365)

    assert result["rate_snapshots_deleted"] == 1
    assert result["history_snapshots_deleted"] == 1
    assert result["days"] == 365

    from sqlalchemy import select

    remaining_rates = (await db_session.execute(select(RateSnapshot))).scalars().all()
    remaining_history = (await db_session.execute(select(HistorySnapshot))).scalars().all()
    assert len(remaining_rates) == 1
    assert remaining_rates[0].fetched_at.replace(tzinfo=timezone.utc) > now - timedelta(days=365)
    assert len(remaining_history) == 1


@pytest.mark.asyncio
async def test_prune_with_no_old_rows_deletes_nothing(db_session):
    """Si todo está dentro de la ventana de retención, no borra nada."""
    now = datetime.now(timezone.utc)
    db_session.add(_make_rate_snapshot(now - timedelta(days=1)))
    await db_session.commit()

    result = await prune_old_rates(db_session, days=365)

    assert result["rate_snapshots_deleted"] == 0
    assert result["history_snapshots_deleted"] == 0


@pytest.mark.asyncio
async def test_prune_uses_custom_days_threshold(db_session):
    """El umbral `days` es configurable, no solo el default de 365."""
    now = datetime.now(timezone.utc)
    db_session.add(_make_rate_snapshot(now - timedelta(days=10)))
    await db_session.commit()

    result = await prune_old_rates(db_session, days=5)

    assert result["rate_snapshots_deleted"] == 1
    assert result["days"] == 5
