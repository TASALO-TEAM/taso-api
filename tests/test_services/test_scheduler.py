"""Tests for APScheduler configuration."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_scheduler_initializes():
    """create_scheduler retorna instancia de AsyncIOScheduler."""
    from src.services.scheduler import create_scheduler
    
    scheduler = create_scheduler()
    
    assert scheduler is not None


@pytest.mark.asyncio
async def test_scheduler_has_refresh_job():
    """create_scheduler configura job 'refresh_all'."""
    from src.services.scheduler import create_scheduler
    
    scheduler = create_scheduler()
    
    jobs = scheduler.get_jobs()
    job_ids = [job.id for job in jobs]
    
    assert 'refresh_all' in job_ids
