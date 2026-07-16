"""APScheduler configuration and jobs."""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Callable, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models.scheduler_status import SchedulerStatus
from src.services.rates_service import fetch_all_sources, save_snapshot, save_history_snapshot
from src.services.stats_service import purge_old_api_request_logs

logger = logging.getLogger(__name__)


def create_scheduler(db_factory: Callable) -> AsyncIOScheduler:
    """
    Crea y configura el scheduler con APScheduler.

    Args:
        db_factory: Factory function que crea sesiones de DB

    Jobs:
    - refresh_all: Ejecuta fetch_all_sources() cada N minutos (env)
    - cubanomic_daily: Ejecuta fetch_cubanomic_daily() a las 00:01 UTC
    - eltoque_image_capture: Captura imagen diaria de ElToque a las 06:00 UTC

    Returns:
        AsyncIOScheduler configurado
    """
    settings = get_settings()
    scheduler = AsyncIOScheduler()

    # Agregar job de refresh (con db_factory bound)
    from functools import partial
    scheduler.add_job(
        partial(refresh_all, db_factory),
        trigger=IntervalTrigger(minutes=settings.refresh_interval_minutes),
        id='refresh_all',
        name='Refresh all rates',
        replace_existing=True
    )

    return scheduler


async def init_scheduler_status(db_factory: Callable) -> None:
    """
    Inicializa el estado del scheduler al arrancar la aplicación.
    Crea un registro inicial si no existe para indicar que el scheduler está activo.

    Args:
        db_factory: Factory function que crea sesiones de DB
    """
    async with db_factory() as session:
        try:
            stmt = select(SchedulerStatus).order_by(SchedulerStatus.id.desc()).limit(1)
            result = await session.execute(stmt)
            status = result.scalars().first()

            if not status:
                status = SchedulerStatus(
                    last_run_at=None,
                    last_success_at=None,
                    error_count=0,
                    last_error=None
                )
                session.add(status)
                await session.commit()
                print("✅ [Scheduler] Estado inicial registrado en DB")
        except Exception as e:
            print(f"⚠️ [Scheduler] No se pudo inicializar el estado: {e}")
            await session.rollback()


async def init_cubanomic_scheduler(
    scheduler: AsyncIOScheduler,
    db_factory: Callable[[], AsyncSession]
) -> None:
    """Initialize Cubanomic daily fetch job at 00:01 UTC."""

    async def fetch_cubanomic_job() -> None:
        db = db_factory()
        try:
            async with db:
                result = await rates_service.fetch_cubanomic_daily(db)
                if result.get("ok"):
                    logger.info(f"🇨🇺 Cubanomic fetch: {result}")
                else:
                    logger.error(f"❌ Cubanomic fetch failed: {result.get('error')}")
        except Exception as e:
            logger.error(f"❌ Cubanomic fetch failed: {e}")

    scheduler.add_job(
        fetch_cubanomic_job,
        trigger="cron",
        hour=0,
        minute=1,
        timezone="UTC",
        id="cubanomic_daily",
        name="Fetch Cubanomic rates daily",
        replace_existing=True,
    )
    print("✅ [Scheduler] Cubanomic daily job added (00:01 UTC)")


async def init_image_capture_scheduler(
    scheduler: AsyncIOScheduler,
    db_factory: Callable[[], AsyncSession]
) -> None:
    """Captura diaria de la imagen de El Toque a las 7:05 hora de Cuba.

    Cron de hora fija (timezone="America/Havana") — corre todos los días
    pase lo que pase, independiente de si algún usuario usó /toqueimg. Usa
    el mismo capture_and_store_image() que el endpoint on-demand: fila y
    archivo únicos (upsert), sin historial por fecha.
    """
    from src.services.image_capture import capture_and_store_image

    async def capture_eltoque_image_job() -> None:
        db = db_factory()
        try:
            async with db:
                result = await capture_and_store_image(db, source="eltoque")
                if result.get("success"):
                    logger.info(
                        "📸 Captura diaria de ElToque OK (stale=%s)",
                        result.get("stale", False),
                    )
                else:
                    logger.error(
                        "❌ Captura diaria de ElToque falló: %s",
                        result.get("error"),
                    )
        except Exception:
            logger.exception("❌ Captura diaria de ElToque falló")

    scheduler.add_job(
        capture_eltoque_image_job,
        trigger="cron",
        hour=7,
        minute=5,
        timezone="America/Havana",
        id="eltoque_image_capture",
        name="Captura diaria imagen ElToque (7:05 Cuba)",
        replace_existing=True,
    )
    print("✅ [Scheduler] ElToque image capture job added (07:05 Cuba)")


async def init_year_scheduler(
    scheduler: AsyncIOScheduler,
    db_factory: Callable[[], AsyncSession]
) -> None:
    """Year daily alert + new year greeting job."""
    from src.services import year_service

    async def year_daily_job() -> None:
        db = db_factory()
        try:
            async with db:
                subs = await year_service.get_enabled_subscriptions(db)
                if not subs:
                    return
                now = datetime.now(timezone.utc)
                progress = await year_service.get_year_progress()
                bar = year_service.generate_progress_bar(progress.percent, length=20)
                status_mood = (
                    "🍀 Recién estamos empezando..." if progress.percent < 2
                    else "🌱 Arrancando motores..." if progress.percent < 10
                    else "🏃‍♂️ Aún hay tiempo de cumplir propósitos." if progress.percent < 50
                    else "🔥 ¡Se nos va el año!" if progress.percent < 80
                    else "🏁 Recta final, ¡agárrate!"
                )
                daily = await year_service.get_daily_quote(db)

                for sub in subs:
                    if sub.hour != now.hour:
                        continue
                    user_id = sub.user_id
                    msg = (
                        f"🗓 *ESTADO DEL AÑO {progress.year}*\n"
                        f"•••\n"
                        f"📆 *Fecha:* {progress.date_str}\n"
                        f"⏳ *Progreso:* `{progress.percent:.2f}%`\n"
                        f"📊 `{bar}`\n\n"
                        f"🔚 Faltan *{progress.days_left} días* para {progress.year + 1}.\n"
                        f"💭 _{status_mood}_\n"
                        f"•••\n"
                        f"💡 *Frase Del Día:*\n"
                        f'"{daily.quote}"'
                    )
                    logger.info("📨 Year alert due for user %s (UTC hour %s)", user_id, now.hour)
        except Exception:
            logger.exception("❌ Year daily job failed")

    # Run every minute — checks subscriptions and dispatches only at matching UTC hour
    scheduler.add_job(
        year_daily_job,
        trigger="cron",
        minute="*",
        timezone="UTC",
        id="year_daily_alert",
        name="Year daily progress alert",
        replace_existing=True,
    )
    print("✅ [Scheduler] Year daily alert job added (checks every minute)")

    async def year_new_year_job() -> None:
        """Daily at midnight UTC: check Jan 1, add greeting if missing, set extra flag."""
        db = db_factory()
        try:
            async with db:
                now = datetime.now(timezone.utc)
                year = now.year
                # Check if January 1 && no greeting yet
                if await year_service.is_new_year(db, year):
                    await year_service.add_new_year_greeting(db, year)
                    logger.info("🎉 New year %s greeting added by cron", year)
                # Ensure extra flag record exists for current year
                await year_service.get_or_create_extra_flag(db, year)
        except Exception:
            logger.exception("❌ Year new-year greeting job failed")

    scheduler.add_job(
        year_new_year_job,
        trigger="cron",
        hour=0,
        minute=0,
        timezone="UTC",
        id="year_new_year_greeting",
        name="Year new year greeting (Jan 1 auto-quote)",
        replace_existing=True,
    )
    print("✅ [Scheduler] Year new-year greeting job added (00:00 UTC daily)")


async def refresh_all(db_factory: Callable) -> None:
    """Job que se ejecuta periódicamente: scrapers → persistencia → history → scheduler_status."""
    print(f"🔄 [Scheduler] Iniciando refresh_all")

    async with db_factory() as session:
        try:
            results = await fetch_all_sources()

            for source, data in results.items():
                if data:
                    await save_snapshot(session, source, data)

            await save_history_snapshot(session, results)

            # Purga de api_request_log > 30 días. Se hace acá (no en un job
            # aparte) para reusar el ciclo existente sin sumar otro cron —
            # es una DELETE indexada, barata incluso corriendo cada 5 min.
            try:
                purged = await purge_old_api_request_logs(session)
                if purged:
                    logger.info("🧹 api_request_log: %d filas > 30 días purgadas", purged)
            except Exception as e:
                logger.warning("⚠️ No se pudo purgar api_request_log: %s", e)

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

            async with db_factory() as error_session:
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
    """Actualiza o crea el registro de scheduler_status."""
    stmt = select(SchedulerStatus).order_by(SchedulerStatus.id.desc()).limit(1)
    result = await session.execute(stmt)
    status = result.scalars().first()

    if status:
        status.last_run_at = last_run_at
        if success:
            status.last_success_at = last_success_at
            status.error_count = 0
            status.last_error = None
        else:
            status.error_count += 1
            status.last_error = error
    else:
        status = SchedulerStatus(
            last_run_at=last_run_at,
            last_success_at=last_success_at,
            error_count=0 if success else 1,
            last_error=None if success else error
        )
        session.add(status)
