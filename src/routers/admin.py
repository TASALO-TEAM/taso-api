"""Router para endpoints admin protegidos."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.middleware.auth import require_auth
from src.models.scheduler_status import SchedulerStatus
from src.services import rates_service
from src.schemas.admin import (
    SchedulerStatusResponse,
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
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_auth)
) -> AdminStatusResponse:
    """
    Obtiene el estado actual del scheduler.

    Returns:
        AdminStatusResponse: Estado del scheduler con última ejecución y errores
    """
    # Obtener el registro de estado del scheduler
    stmt = select(SchedulerStatus).order_by(SchedulerStatus.id.desc()).limit(1)
    result = await db.execute(stmt)
    status = result.scalars().first()

    if status:
        scheduler_status = SchedulerStatusResponse(
            last_run_at=status.last_run_at,
            last_success_at=status.last_success_at,
            error_count=status.error_count,
            last_error=status.last_error,
            updated_at=status.updated_at
        )
    else:
        # No hay registros aún
        now = datetime.now(timezone.utc)
        scheduler_status = SchedulerStatusResponse(
            last_run_at=None,
            last_success_at=None,
            error_count=0,
            last_error=None,
            updated_at=now
        )

    return AdminStatusResponse(
        ok=True,
        scheduler=scheduler_status,
        updated_at=datetime.now(timezone.utc)
    )
