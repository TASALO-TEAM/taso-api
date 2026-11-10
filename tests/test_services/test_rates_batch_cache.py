"""Tests del lote de 'tasa anterior', la caché en memoria de lecturas y el ETag de /latest y /eltoque."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import Response

from src.models.rate_snapshot import RateSnapshot
from src.routers import rates as rates_router
from src.services import rates_service as rs

T0 = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


async def _seed(db) -> None:
    """3 ciclos de ElToque (USD, EUR) y QvaPay (BANK_CUP). TRX solo existe en el último ciclo."""
    rows = []
    for i, (usd, eur) in enumerate([(900, 1000), (905, 1000), (910, 990)]):
        ts = T0 + timedelta(minutes=15 * i)
        rows += [
            RateSnapshot(source="eltoque", currency="USD", sell_rate=usd, fetched_at=ts),
            RateSnapshot(source="eltoque", currency="EUR", sell_rate=eur, fetched_at=ts),
            RateSnapshot(source="qvapay", currency="BANK_CUP", buy_rate=usd - 5, sell_rate=usd + 5, fetched_at=ts),
        ]
    rows.append(RateSnapshot(source="eltoque", currency="TRX", sell_rate=5, fetched_at=T0 + timedelta(minutes=30)))
    db.add_all(rows)
    await db.commit()


async def _latest_cycle(db, source: str) -> list[RateSnapshot]:
    snaps = (await db.execute(select(RateSnapshot).where(RateSnapshot.source == source))).scalars().all()
    newest = max(s.fetched_at for s in snaps)
    return [s for s in snaps if s.fetched_at == newest]


@pytest.mark.asyncio
async def test_previous_rates_map_equals_legacy_per_currency(db_session):
    await _seed(db_session)

    eltoque = await _latest_cycle(db_session, "eltoque")
    got = await rs._previous_rates_map(db_session, "eltoque", eltoque)
    for snap in eltoque:
        legacy = await rs._get_previous_snapshot(db_session, "eltoque", snap.currency, snap.fetched_at)
        assert got[snap.currency] == legacy
    assert got["USD"] == 905.0 and got["EUR"] == 1000.0
    assert got["TRX"] is None  # sin historial previo

    qvapay = await _latest_cycle(db_session, "qvapay")
    got_qp = await rs._previous_rates_map(db_session, "qvapay", qvapay)
    legacy_qp = await rs._get_previous_qvapay_average(db_session, "BANK_CUP", qvapay[0].fetched_at)
    assert got_qp["BANK_CUP"] == legacy_qp


@pytest.mark.asyncio
async def test_previous_rates_map_is_a_single_query(db_session):
    await _seed(db_session)
    eltoque = await _latest_cycle(db_session, "eltoque")

    calls = 0
    original = db_session.execute

    async def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return await original(*args, **kwargs)

    db_session.execute = counted
    try:
        await rs._previous_rates_map(db_session, "eltoque", eltoque)
    finally:
        db_session.execute = original
    assert calls == 1


@pytest.mark.asyncio
async def test_previous_rates_map_empty_snapshots():
    assert await rs._previous_rates_map(None, "eltoque", []) == {}


@pytest.mark.asyncio
async def test_latest_cache_hit_isolation_and_invalidation():
    calls = 0

    async def fake(session, max_age_minutes):
        nonlocal calls
        calls += 1
        return {"eltoque": {"USD": {"rate": 1.0}}}

    with patch.object(rs, "_compute_latest_rates", fake):
        first = await rs.get_latest_rates(None, 120, use_cache=True)
        second = await rs.get_latest_rates(None, 120, use_cache=True)
        assert calls == 1 and first == second

        second["eltoque"]["USD"]["rate"] = 99.0  # mutar la copia no contamina la caché
        assert (await rs.get_latest_rates(None, 120, use_cache=True))["eltoque"]["USD"]["rate"] == 1.0

        await rs.get_latest_rates(None, 60, use_cache=True)  # otro max_age → otra clave
        assert calls == 2

        rs.invalidate_rates_cache()
        await rs.get_latest_rates(None, 120, use_cache=True)
        assert calls == 3


@pytest.mark.asyncio
async def test_latest_without_cache_flag_always_computes_and_empty_is_not_cached():
    calls = 0

    async def empty(session, max_age_minutes):
        nonlocal calls
        calls += 1
        return {"eltoque": {}, "bcc": {}}

    with patch.object(rs, "_compute_latest_rates", empty):
        await rs.get_latest_rates(None, 120)
        await rs.get_latest_rates(None, 120)
        assert calls == 2
        await rs.get_latest_rates(None, 120, use_cache=True)
        await rs.get_latest_rates(None, 120, use_cache=True)  # vacío: no se cachea
        assert calls == 4


@pytest.mark.asyncio
async def test_latest_cache_expires_after_ttl():
    calls = 0

    async def fake(session, max_age_minutes):
        nonlocal calls
        calls += 1
        return {"eltoque": {"USD": {"rate": 1.0}}}

    with patch.object(rs, "_compute_latest_rates", fake), patch.object(rs, "RATES_CACHE_TTL_SECONDS", 0.0):
        await rs.get_latest_rates(None, 120, use_cache=True)
        await rs.get_latest_rates(None, 120, use_cache=True)
    assert calls == 2


def _request(if_none_match: str | None = None) -> Request:
    headers = [(b"if-none-match", if_none_match.encode())] if if_none_match else []
    return Request({"type": "http", "headers": headers})


def test_conditional_sets_headers_then_returns_304_on_match():
    stamps = {"eltoque": T0}
    resp = Response()
    assert rates_router._conditional(_request(), resp, "latest|120", stamps) is None
    etag = resp.headers["ETag"]
    assert resp.headers["Cache-Control"] == rates_router.CACHE_CONTROL

    not_modified = rates_router._conditional(_request(etag), Response(), "latest|120", stamps)
    assert not_modified is not None and not_modified.status_code == 304
    assert not_modified.headers["ETag"] == etag

    # tasas nuevas (otro fetched_at) → otro ETag → respuesta completa
    newer = {"eltoque": T0 + timedelta(minutes=15)}
    assert rates_router._conditional(_request(etag), Response(), "latest|120", newer) is None
    # otro parámetro → otro ETag
    assert rates_router._conditional(_request(etag), Response(), "latest|60", stamps) is None


def test_conditional_without_data_adds_no_etag():
    resp = Response()
    assert rates_router._conditional(_request(), resp, "latest|120", {}) is None
    assert "ETag" not in resp.headers
