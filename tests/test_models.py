"""Tests para los modelos de base de datos."""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.rate_snapshot import RateSnapshot
from src.models.scheduler_status import SchedulerStatus


@pytest.fixture
async def db_session():
    """Crear sesión de DB en memoria para tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    
    await engine.dispose()


@pytest.mark.asyncio
async def test_rate_snapshot_creation(db_session):
    """RateSnapshot se crea correctamente."""
    snapshot = RateSnapshot(
        source="eltoque",
        currency="USD",
        buy_rate=None,
        sell_rate=Decimal("365.00"),
        fetched_at=datetime.now(timezone.utc),
    )
    
    db_session.add(snapshot)
    await db_session.commit()
    await db_session.refresh(snapshot)
    
    assert snapshot.id is not None
    assert snapshot.source == "eltoque"
    assert snapshot.currency == "USD"
    assert snapshot.sell_rate == Decimal("365.00")
    assert snapshot.created_at is not None


@pytest.mark.asyncio
async def test_scheduler_status_creation(db_session):
    """SchedulerStatus se crea correctamente."""
    status = SchedulerStatus(
        last_run_at=datetime.now(timezone.utc),
        last_success_at=datetime.now(timezone.utc),
        error_count=0,
        last_error=None,
    )
    
    db_session.add(status)
    await db_session.commit()
    await db_session.refresh(status)
    
    assert status.id is not None
    assert status.error_count == 0


@pytest.mark.asyncio
async def test_scheduler_status_error_update(db_session):
    """SchedulerStatus actualiza contador de errores."""
    status = SchedulerStatus(
        last_run_at=datetime.now(timezone.utc),
        error_count=0,
    )
    
    db_session.add(status)
    await db_session.commit()
    
    status.error_count = 3
    status.last_error = "Connection timeout"
    await db_session.commit()
    
    assert status.error_count == 3
    assert status.last_error == "Connection timeout"
