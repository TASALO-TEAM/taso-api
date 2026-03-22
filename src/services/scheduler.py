"""APScheduler configuration and jobs."""

from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from sqlalchemy import select

from src.config import get_settings
from src.database import async_session_factory
from src.models.scheduler_status import SchedulerStatus
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

            # 3. Actualizar scheduler_status con éxito
            await _update_scheduler_status(
                session,
                success=True,
                last_run_at=datetime.now(timezone.utc),
                last_success_at=datetime.now(timezone.utc),
                error=None
            )

            await session.commit()
            print(f"✅ [Scheduler] refresh_all completado exitosamente")

        except Exception as e:
            print(f"❌ [Scheduler] Error en refresh_all: {e}")
            await session.rollback()
            
            # Actualizar scheduler_status con error
            async with async_session_factory() as error_session:
                await _update_scheduler_status(
                    error_session,
                    success=False,
                    last_run_at=datetime.now(timezone.utc),
                    error=str(e)
                )
                await error_session.commit()
            
            raise


async def _update_scheduler_status(
    session,
    success: bool,
    last_run_at: datetime,
    last_success_at: datetime | None = None,
    error: str | None = None
) -> None:
    """
    Actualiza o crea el registro de scheduler_status.

    Args:
        session: SQLAlchemy async session
        success: Si la ejecución fue exitosa
        last_run_at: Timestamp de la ejecución
        last_success_at: Timestamp del último éxito (None si falló)
        error: Mensaje de error si ocurrió
    """
    # Obtener registro existente
    stmt = select(SchedulerStatus).order_by(SchedulerStatus.id.desc()).limit(1)
    result = await session.execute(stmt)
    status = result.scalar_first()

    if status:
        # Actualizar existente
        status.last_run_at = last_run_at
        if success:
            status.last_success_at = last_success_at
            status.error_count = 0
            status.last_error = None
        else:
            status.error_count += 1
            status.last_error = error
    else:
        # Crear nuevo registro
        status = SchedulerStatus(
            last_run_at=last_run_at,
            last_success_at=last_success_at,
            error_count=0 if success else 1,
            last_error=None if success else error
        )
        session.add(status)
