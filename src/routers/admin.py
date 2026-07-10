"""Router para endpoints admin protegidos."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.middleware.auth import require_auth
from src.models.scheduler_status import SchedulerStatus
from src.services import rates_service
from src.schemas.admin import (
    SchedulerJobInfo,
    AdminStatusResponse,
    RefreshResult,
    RefreshData,
    RefreshResponse,
)


router = APIRouter(dependencies=[Depends(require_auth)])


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_rates(
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_auth)
) -> RefreshResponse:
    """
    Dispara un refresh inmediato de todas las fuentes de tasas.

    Ejecuta los 4 scrapers (ElToque, Binance, CADECA, BCC) en paralelo
    y persiste los resultados en la base de datos.

    Returns:
        RefreshResponse: Resultados del refresh por fuente
    """
    results = await rates_service.fetch_all_sources()

    refresh_results = []
    total_success = 0
    total_failed = 0

    for source, data in results.items():
        if data is None:
            refresh_results.append(RefreshResult(
                source=source,
                success=False,
                currencies_count=0,
                error="No data returned from scraper"
            ))
            total_failed += 1
        else:
            # Contar monedas obtenidas
            currencies_count = len(data) if isinstance(data, (dict, list)) else 0
            
            # Guardar snapshot
            await rates_service.save_snapshot(db, source, data)
            
            refresh_results.append(RefreshResult(
                source=source,
                success=True,
                currencies_count=currencies_count,
                error=None
            ))
            total_success += 1

    await db.commit()

    return RefreshResponse(
        ok=True,
        data=RefreshData(
            results=refresh_results,
            total_success=total_success,
            total_failed=total_failed
        ),
        completed_at=datetime.now(timezone.utc)
    )


@router.get("/status", response_model=AdminStatusResponse)
async def get_scheduler_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_auth)
) -> AdminStatusResponse:
    """
    Obtiene el estado de TODOS los jobs registrados en el scheduler.

    Antes solo exponía el job "refresh_all" (con envoltorio {scheduler:
    {...}}); ahora lista cualquier job de APScheduler (cubanomic_daily,
    year_daily_alert, etc.), agregando last_run/last_success/error_count/
    last_error solo para "refresh_all", que es el único con tracking
    persistido en la tabla scheduler_status. Ver
    docs/plans/2026-07-08-status-command-v2.md (Fase 2).

    Returns:
        AdminStatusResponse: is_scheduler_running + lista de jobs
    """
    scheduler = request.app.state.scheduler
    is_scheduler_running = bool(scheduler and scheduler.running)

    # Tracking persistido — hoy solo existe para "refresh_all"
    stmt = select(SchedulerStatus).order_by(SchedulerStatus.id.desc()).limit(1)
    result = await db.execute(stmt)
    refresh_status = result.scalars().first()

    jobs: list[SchedulerJobInfo] = []
    apscheduler_jobs = scheduler.get_jobs() if scheduler else []
    for job in apscheduler_jobs:
        job_info = SchedulerJobInfo(
            id=job.id,
            name=job.name,
            next_run_at=getattr(job, "next_run_time", None),
        )
        if job.id == "refresh_all" and refresh_status:
            job_info.last_run_at = refresh_status.last_run_at
            job_info.last_success_at = refresh_status.last_success_at
            job_info.error_count = refresh_status.error_count
            job_info.last_error = refresh_status.last_error
        jobs.append(job_info)

    return AdminStatusResponse(
        ok=True,
        is_scheduler_running=is_scheduler_running,
        jobs=jobs,
        updated_at=datetime.now(timezone.utc),
    )
