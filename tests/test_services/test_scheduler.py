"""Tests for APScheduler configuration."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_scheduler_initializes():
    """create_scheduler retorna instancia de AsyncIOScheduler."""
    from src.services.scheduler import create_scheduler

    # Mock db_factory
    db_factory = MagicMock()
    scheduler = create_scheduler(db_factory)

    assert scheduler is not None


@pytest.mark.asyncio
async def test_scheduler_has_refresh_job():
    """create_scheduler configura job 'refresh_all'."""
    from src.services.scheduler import create_scheduler

    # Mock db_factory
    db_factory = MagicMock()
    scheduler = create_scheduler(db_factory)

    jobs = scheduler.get_jobs()
    job_ids = [job.id for job in jobs]

    assert 'refresh_all' in job_ids


@pytest.mark.asyncio
async def test_cubanomic_scheduler_can_be_initialized():
    """init_cubanomic_scheduler agrega job 'cubanomic_daily'."""
    from src.services.scheduler import create_scheduler, init_cubanomic_scheduler

    # Mock db_factory
    db_factory = MagicMock()
    scheduler = create_scheduler(db_factory)
    
    # Initialize Cubanomic scheduler
    await init_cubanomic_scheduler(scheduler, db_factory)

    jobs = scheduler.get_jobs()
    job_ids = [job.id for job in jobs]

    assert 'cubanomic_daily' in job_ids
