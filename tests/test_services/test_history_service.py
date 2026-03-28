"""Tests for save_history_snapshot() service function."""

import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from src.models.rates import HistorySnapshot


@pytest.mark.asyncio
async def test_save_history_snapshot_saves_all_fields(db_session):
    """Save history snapshot stores all rate fields correctly."""
    from src.services.rates_service import save_history_snapshot

    rates_data = {
        "eltoque": {
            "USD": {"rate": 517.26, "change": "up"},
            "EUR": {"rate": 582.36, "change": "up"},
            "MLC": {"rate": 394.82, "change": "neutral"},
        },
        "cadeca": {
            "USD": {"buy": 515.00, "sell": 525.00},
            "EUR": {"buy": 580.00, "sell": 590.00},
            "MLC": {"buy": 390.00, "sell": 400.00},
        },
        "bcc": {
            "USD": {"buy": 514.50, "sell": 524.50},
            "EUR": {"buy": 579.50, "sell": 589.50},
            "MLC": {"buy": 389.50, "sell": 399.50},
        },
        "binance": {
            "BTC": {"rate": 95000.00},
            "ETH": {"rate": 3500.00},
        },
    }

    await save_history_snapshot(db_session, rates_data)

    # Verify snapshot was saved
    snapshots = await db_session.execute(
        select(HistorySnapshot).order_by(HistorySnapshot.fetched_at.desc())
    )
    snapshot = snapshots.scalars().first()

    assert snapshot is not None
    assert snapshot.eltoque_usd == 517.26
    assert snapshot.eltoque_eur == 582.36
    assert snapshot.eltoque_mlc == 394.82
    assert snapshot.cadeca_usd == 520.00  # (515 + 525) / 2
    assert snapshot.cadeca_eur == 585.00  # (580 + 590) / 2
    assert snapshot.cadeca_mlc == 395.00  # (390 + 400) / 2
    assert snapshot.bcc_usd == 519.50  # (514.50 + 524.50) / 2
    assert snapshot.bcc_eur == 584.50  # (579.50 + 589.50) / 2
    assert snapshot.bcc_mlc == 394.50  # (389.50 + 399.50) / 2
    assert snapshot.binance_btc == 95000.00
    assert snapshot.binance_eth == 3500.00


@pytest.mark.asyncio
async def test_save_history_snapshot_handles_missing_data(db_session):
    """Save history snapshot handles missing rate data gracefully."""
    from src.services.rates_service import save_history_snapshot

    rates_data = {
        "eltoque": {},  # Empty
        "cadeca": {"USD": {"buy": 515.00}},  # Partial (no sell)
        "bcc": {"EUR": {"sell": 580.00}},  # Partial (no buy)
        "binance": {},  # Empty
    }

    await save_history_snapshot(db_session, rates_data)

    # Should not raise, should save with None for missing fields
    snapshots = await db_session.execute(
        select(HistorySnapshot).order_by(HistorySnapshot.fetched_at.desc())
    )
    snapshot = snapshots.scalars().first()

    assert snapshot is not None
    assert snapshot.eltoque_usd is None
    assert snapshot.eltoque_eur is None
    assert snapshot.eltoque_mlc is None
    assert snapshot.cadeca_usd == 515.00  # Only buy, no sell
    assert snapshot.cadeca_eur is None
    assert snapshot.cadeca_mlc is None
    assert snapshot.bcc_usd is None
    assert snapshot.bcc_eur == 580.00  # Only sell, no buy
    assert snapshot.bcc_mlc is None
    assert snapshot.binance_btc is None
    assert snapshot.binance_eth is None


@pytest.mark.asyncio
async def test_save_history_snapshot_handles_none_values(db_session):
    """Save history snapshot handles None values in rate data."""
    from src.services.rates_service import save_history_snapshot

    rates_data = {
        "eltoque": {
            "USD": {"rate": None, "change": "up"},  # None rate
        },
        "cadeca": {
            "USD": {"buy": None, "sell": None},  # Both None
        },
        "binance": {
            "BTC": {"rate": 95000.00},
        },
    }

    await save_history_snapshot(db_session, rates_data)

    snapshots = await db_session.execute(
        select(HistorySnapshot).order_by(HistorySnapshot.fetched_at.desc())
    )
    snapshot = snapshots.scalars().first()

    assert snapshot is not None
    assert snapshot.eltoque_usd is None  # None rate handled
    assert snapshot.cadeca_usd is None  # Both None handled
    assert snapshot.binance_btc == 95000.00


@pytest.mark.asyncio
async def test_average_cadeca_rate_with_buy_and_sell():
    """_average_cadeca_rate returns average when both buy and sell present."""
    from src.services.rates_service import _average_cadeca_rate

    rate_data = {"buy": 515.00, "sell": 525.00}
    result = _average_cadeca_rate(rate_data)

    assert result == 520.00


@pytest.mark.asyncio
async def test_average_cadeca_rate_with_only_buy():
    """_average_cadeca_rate returns buy when sell is missing."""
    from src.services.rates_service import _average_cadeca_rate

    rate_data = {"buy": 515.00}
    result = _average_cadeca_rate(rate_data)

    assert result == 515.00


@pytest.mark.asyncio
async def test_average_cadeca_rate_with_only_sell():
    """_average_cadeca_rate returns sell when buy is missing."""
    from src.services.rates_service import _average_cadeca_rate

    rate_data = {"sell": 525.00}
    result = _average_cadeca_rate(rate_data)

    assert result == 525.00


@pytest.mark.asyncio
async def test_average_cadeca_rate_with_empty_dict():
    """_average_cadeca_rate returns None for empty dict."""
    from src.services.rates_service import _average_cadeca_rate

    rate_data = {}
    result = _average_cadeca_rate(rate_data)

    assert result is None


@pytest.mark.asyncio
async def test_average_cadeca_rate_with_none():
    """_average_cadeca_rate returns None for None input."""
    from src.services.rates_service import _average_cadeca_rate

    result = _average_cadeca_rate(None)

    assert result is None
