"""Tests de la fuente QvaPay en rates_service."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from src.models.rate_snapshot import RateSnapshot
from src.services.rates_service import (
    _format_qvapay_snapshot,
    _get_previous_qvapay_average,
    _normalize_qvapay_data,
    _qvapay_average,
    save_snapshot,
)


def test_qvapay_average_both_sides():
    assert _qvapay_average(978.31, 984.78) == pytest.approx(981.545)


def test_qvapay_average_single_side_is_that_side():
    assert _qvapay_average(1.45, None) == 1.45
    assert _qvapay_average(None, 1.5) == 1.5
    assert _qvapay_average(None, None) is None


def test_normalize_qvapay_skips_empty_and_keeps_one_side():
    data = {
        "CUP": {"buy": 978.31, "sell": 984.78},
        "ZELLE": {"buy": 1.02, "sell": None},
        "SBERBANK": {"buy": None, "sell": None},
    }

    result = {r["currency"]: r for r in _normalize_qvapay_data(data)}

    assert set(result) == {"CUP", "ZELLE"}
    assert result["CUP"]["buy_rate"] == 978.31
    assert result["CUP"]["sell_rate"] == 984.78
    assert result["ZELLE"]["buy_rate"] == 1.02
    assert result["ZELLE"]["sell_rate"] is None


def test_format_qvapay_snapshot_average_and_change():
    snap = RateSnapshot(source="qvapay", currency="CUP", buy_rate=978.31, sell_rate=984.78)

    up = _format_qvapay_snapshot(snap, 975.0)
    assert up["rate"] == pytest.approx(981.545)
    assert up["buy"] == pytest.approx(978.31)
    assert up["sell"] == pytest.approx(984.78)
    assert up["change"] == "up"
    assert up["prev_rate"] == 975.0

    down = _format_qvapay_snapshot(snap, 990.0)
    assert down["change"] == "down"

    first = _format_qvapay_snapshot(snap, None)
    assert first["change"] == "neutral"


def test_format_qvapay_snapshot_single_side():
    snap = RateSnapshot(source="qvapay", currency="ZELLE", buy_rate=1.02, sell_rate=None)

    info = _format_qvapay_snapshot(snap, None)

    assert info["rate"] == pytest.approx(1.02)
    assert info["buy"] == pytest.approx(1.02)
    assert info["sell"] is None


def test_format_qvapay_snapshot_without_sides_is_none():
    snap = RateSnapshot(source="qvapay", currency="X", buy_rate=None, sell_rate=None)
    assert _format_qvapay_snapshot(snap, None) is None


@pytest.mark.asyncio
async def test_save_snapshot_qvapay_stores_buy_and_sell(db_session):
    data = {
        "CUP": {"buy": 978.31, "sell": 984.78},
        "ZELLE": {"buy": 1.02, "sell": None},
    }

    await save_snapshot(db_session, "qvapay", data)
    await db_session.commit()

    rows = (
        await db_session.execute(select(RateSnapshot).where(RateSnapshot.source == "qvapay"))
    ).scalars().all()
    by_currency = {r.currency: r for r in rows}

    assert set(by_currency) == {"CUP", "ZELLE"}
    assert float(by_currency["CUP"].buy_rate) == pytest.approx(978.31)
    assert float(by_currency["CUP"].sell_rate) == pytest.approx(984.78)
    assert by_currency["ZELLE"].sell_rate is None


@pytest.mark.asyncio
async def test_save_snapshot_qvapay_none_saves_nothing(db_session):
    await save_snapshot(db_session, "qvapay", None)
    await db_session.commit()

    rows = (await db_session.execute(select(RateSnapshot))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_previous_qvapay_average_uses_average_of_previous_snapshot(db_session):
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            RateSnapshot(source="qvapay", currency="CUP", buy_rate=970.0, sell_rate=980.0,
                         fetched_at=now - timedelta(minutes=30)),
            RateSnapshot(source="qvapay", currency="CUP", buy_rate=972.0, sell_rate=982.0,
                         fetched_at=now - timedelta(minutes=15)),
            RateSnapshot(source="qvapay", currency="CUP", buy_rate=978.0, sell_rate=984.0,
                         fetched_at=now),
        ]
    )
    await db_session.commit()

    prev = await _get_previous_qvapay_average(db_session, "CUP", now)

    assert prev == pytest.approx(977.0)


@pytest.mark.asyncio
async def test_previous_qvapay_average_none_without_history(db_session):
    prev = await _get_previous_qvapay_average(db_session, "CUP", datetime.now(timezone.utc))
    assert prev is None
