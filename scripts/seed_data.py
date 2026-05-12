#!/usr/bin/env python3
"""
Seed test data into taso-api database.

This script creates sample records for all models to verify database connectivity
and provide initial data for development/testing.

Usage:
    cd taso-api
    python scripts/seed_data.py [--clear] [--quiet]

Options:
    --clear    Clear all existing data before seeding (DANGEROUS: deletes all rows)
    --quiet    Suppress informational messages
"""

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.database import get_engine, get_session_maker
from src.models.rate_snapshot import RateSnapshot
from src.models.scheduler_status import SchedulerStatus
from src.models.rates import CubanomicRate, HistorySnapshot
from src.models.image_snapshot import ImageSnapshot
from src.models.image_alert import UserImageAlert
from src.models.bot_stats import BotUser, BotCommandStat


async def clear_all_tables(db: AsyncSession) -> None:
    """Delete all data from all tables in correct order (respecting FKs)."""
    # Delete in child-first order
    await db.execute(delete(BotCommandStat))
    await db.execute(delete(UserImageAlert))
    await db.execute(delete(BotUser))
    await db.execute(delete(RateSnapshot))
    await db.execute(delete(CubanomicRate))
    await db.execute(delete(HistorySnapshot))
    await db.execute(delete(ImageSnapshot))
    await db.execute(delete(SchedulerStatus))
    await db.commit()
    print("✓ All tables cleared")


async def get_or_create_bot_user(db: AsyncSession, user_id: int) -> BotUser:
    """Get existing BotUser or create a new one."""
    result = await db.execute(select(BotUser).where(BotUser.user_id == user_id))
    user = result.scalars().first()
    if user:
        return user
    user = BotUser(
        user_id=user_id,
        username="test_user",
        first_name="Test",
        total_commands=0
    )
    db.add(user)
    await db.flush()  # Assigns PK
    return user


async def seed_bot_user(db: AsyncSession, quiet: bool = False) -> BotUser:
    """Create or get a BotUser for testing."""
    user = await get_or_create_bot_user(db, user_id=123456789)
    if not quiet:
        print(f"✓ BotUser: {user}")
    return user


async def seed_user_image_alert(db: AsyncSession, user: BotUser, quiet: bool = False) -> UserImageAlert:
    """Create or update a UserImageAlert for the given user."""
    # Upsert pattern
    from sqlalchemy.dialects.postgresql import insert

    stmt = insert(UserImageAlert).values(
        user_id=user.user_id,
        alert_time="07:30",
        format_type="photo",
        enabled=True
    ).on_conflict_do_update(
        index_elements=["user_id"],
        set_={
            "alert_time": "07:30",
            "format_type": "photo",
            "enabled": True
        }
    ).returning(UserImageAlert)

    result = await db.execute(stmt)
    alert = result.scalars().first()
    if not quiet:
        print(f"✓ UserImageAlert: user_id={user.user_id}, time={alert.alert_time}, enabled={alert.enabled}")
    return alert


async def seed_bot_command_stat(db: AsyncSession, user: BotUser, quiet: bool = False) -> BotCommandStat:
    """Create a sample BotCommandStat record."""
    stat = BotCommandStat(
        command="/start",
        user_id=user.user_id,
        username=user.username,
        source=None,
        success=True
    )
    db.add(stat)
    await db.flush()
    if not quiet:
        print(f"✓ BotCommandStat: {stat}")
    return stat


async def seed_rate_snapshots(db: AsyncSession, quiet: bool = False) -> list[RateSnapshot]:
    """Create sample rate snapshots from multiple sources."""
    snapshots = []
    now = datetime.now(timezone.utc)

    # ElToque USD (sell rate only)
    snap = RateSnapshot(
        source="eltoque",
        currency="USD",
        buy_rate=None,
        sell_rate=Decimal("365.50"),
        fetched_at=now
    )
    db.add(snap)
    snapshots.append(snap)
    if not quiet:
        print(f"✓ RateSnapshot: eltoque USD sell={snap.sell_rate}")

    # CADECA USD (buy & sell)
    snap = RateSnapshot(
        source="cadeca",
        currency="USD",
        buy_rate=Decimal("362.00"),
        sell_rate=Decimal("368.00"),
        fetched_at=now
    )
    db.add(snap)
    snapshots.append(snap)
    if not quiet:
        print(f"✓ RateSnapshot: cadeca USD buy={snap.buy_rate} sell={snap.sell_rate}")

    # BCC EUR
    snap = RateSnapshot(
        source="bcc",
        currency="EUR",
        buy_rate=Decimal("335.00"),
        sell_rate=Decimal("342.00"),
        fetched_at=now
    )
    db.add(snap)
    snapshots.append(snap)
    if not quiet:
        print(f"✓ RateSnapshot: bcc EUR buy={snap.buy_rate} sell={snap.sell_rate}")

    # Binance BTC (crypto)
    snap = RateSnapshot(
        source="binance",
        currency="BTC",
        buy_rate=None,  # crypto usually just price
        sell_rate=Decimal("95000.00"),
        fetched_at=now
    )
    db.add(snap)
    snapshots.append(snap)
    if not quiet:
        print(f"✓ RateSnapshot: binance BTC price={snap.sell_rate}")

    return snapshots


async def seed_cubanomic_rate(db: AsyncSession, quiet: bool = False) -> CubanomicRate:
    """Create a CubanomicRate record (daily aggregate)."""
    rate = CubanomicRate(
        usd_rate=Decimal("360.00"),
        eur_rate=Decimal("330.00"),
        mlc_rate=Decimal("240.00"),
        fetched_at=datetime.now(timezone.utc)
    )
    db.add(rate)
    if not quiet:
        print(f"✓ CubanomicRate: USD={rate.usd_rate}, EUR={rate.eur_rate}, MLC={rate.mlc_rate}")
    return rate


async def seed_history_snapshot(db: AsyncSession, quiet: bool = False) -> HistorySnapshot:
    """Create a HistorySnapshot (aggregated 5-min snapshot)."""
    snap = HistorySnapshot(
        fetched_at=datetime.now(timezone.utc),
        eltoque_usd=365.50,
        eltoque_eur=355.00,
        eltoque_mlc=245.00,
        cadeca_usd=362.00,
        cadeca_eur=335.00,
        cadeca_mlc=240.00,
        bcc_usd=363.00,
        bcc_eur=336.00,
        bcc_mlc=241.00,
        binance_btc=95000.00,
        binance_eth=2500.00
    )
    db.add(snap)
    if not quiet:
        print(f"✓ HistorySnapshot: fetched_at={snap.fetched_at}")
    return snap


async def seed_image_snapshot(db: AsyncSession, quiet: bool = False) -> ImageSnapshot:
    """Create an ImageSnapshot record."""
    snap = ImageSnapshot(
        source="eltoque",
        image_path="/var/www/tasalo/images/eltoque_20250512.jpg",
        thumbnail_path="/var/www/tasalo/thumbs/eltoque_20250512_thumb.jpg",
        file_size=245760,  # 240 KB
        captured_at=datetime.now(timezone.utc),
        extra_data={
            "url": "https://tasas.eltoque.com/screenshot.jpg",
            "width": 1200,
            "height": 800,
            "format": "jpeg"
        }
    )
    db.add(snap)
    if not quiet:
        print(f"✓ ImageSnapshot: id will be assigned, source={snap.source}")
    return snap


async def seed_scheduler_status(db: AsyncSession, quiet: bool = False) -> SchedulerStatus:
    """Create a SchedulerStatus record (tracking scheduler health)."""
    status = SchedulerStatus(
        last_run_at=datetime.now(timezone.utc),
        last_success_at=datetime.now(timezone.utc),
        error_count=0,
        last_error=None
    )
    db.add(status)
    if not quiet:
        print(f"✓ SchedulerStatus: last_run={status.last_run_at}")
    return status


async def seed_all(clear: bool = False, quiet: bool = False) -> None:
    """Main seeding function: creates sample data for all models."""
    settings = get_settings()
    engine = get_engine(settings.database_url, echo=not quiet)
    session_factory = get_session_maker(engine)

    async with session_factory() as db:
        try:
            if clear:
                await clear_all_tables(db)

            if not quiet:
                print("\nSeeding database...\n")

            # Order matters due to foreign keys
            user = await seed_bot_user(db, quiet)
            await seed_user_image_alert(db, user, quiet)
            await seed_bot_command_stat(db, user, quiet)

            await seed_rate_snapshots(db, quiet)
            await seed_cubanomic_rate(db, quiet)
            await seed_history_snapshot(db, quiet)
            await seed_image_snapshot(db, quiet)
            await seed_scheduler_status(db, quiet)

            await db.commit()

            if not quiet:
                print("\n✅ All sample data created successfully.\n")

        except Exception as e:
            await db.rollback()
            print(f"\n❌ Error seeding database: {e}\n", file=sys.stderr)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed test data into taso-api database")
    parser.add_argument("--clear", action="store_true", help="Clear all data before seeding")
    parser.add_argument("--quiet", action="store_true", help="Suppress informational output")
    args = parser.parse_args()

    try:
        asyncio.run(seed_all(clear=args.clear, quiet=args.quiet))
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
