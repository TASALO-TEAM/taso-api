"""APScheduler configuration and jobs."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.config import get_settings
from src.database import async_session_factory
from src.services.rates_service import fetch_all_sources, save_snapshot


def create_scheduler() -> AsyncIOScheduler:
    """
    Crea y configura el scheduler con APScheduler.
    
    Jobs:
    - refresh_all: Ejecuta fetch_all_sources() cada N minutos (env)
    
    Returns:
        AsyncIOScheduler configurado
    """
    settings = get_settings()
    scheduler = AsyncIOScheduler()
    
    # Agregar job de refresh
    scheduler.add_job(
        refresh_all,
        trigger=IntervalTrigger(minutes=settings.refresh_interval_minutes),
        id='refresh_all',
        name='Refresh all rates',
        replace_existing=True
    )
    
    return scheduler


async def refresh_all() -> None:
    """
    Job que se ejecuta periódicamente:
    1. Ejecuta los 4 scrapers en paralelo
    2. Persiste snapshots en PostgreSQL
    3. Actualiza scheduler_status
    
    Legacy pattern: bucle principal de legacy/tasa.py
    """
    print(f"🔄 [Scheduler] Iniciando refresh_all")
    
    async with async_session_factory() as session:
        try:
            # 1. Fetch all sources
            results = await fetch_all_sources()
            
            # 2. Save snapshots
            for source, data in results.items():
                if data:
                    await save_snapshot(session, source, data)
            
            await session.commit()
            print(f"✅ [Scheduler] refresh_all completado exitosamente")
            
        except Exception as e:
            print(f"❌ [Scheduler] Error en refresh_all: {e}")
            await session.rollback()
            # TODO: Actualizar scheduler_status con error (Fase 5)
            raise
