"""Router para endpoints de estadísticas del bot."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request

from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.middleware.auth import require_auth
from src.schemas.stats import (
    BotStatsSummary,
    TrackCommandRequest,
    TrackCommandResponse,
)
from src.services import stats_service


router = APIRouter(dependencies=[Depends(require_auth)])


@router.post("/track", response_model=TrackCommandResponse)
async def track_command(
    request: TrackCommandRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_auth),
) -> TrackCommandResponse:
    """
    Registra el uso de un comando del bot.

    Endpoint llamado por taso-bot cada vez que se ejecuta un comando.

    Args:
        request: Datos del comando a trackear
        db: Database session
        api_key: API key de autenticación

    Returns:
        TrackCommandResponse: Confirmación del trackeo
    """
    await stats_service.track_command(
        session=db,
        command=request.command,
        user_id=request.user_id,
        username=request.username,
        source=request.source,
        success=request.success,
    )

    return TrackCommandResponse(ok=True, message="Comando trackeado")


@router.get("/summary", response_model=BotStatsSummary)
async def get_stats_summary(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_auth),
) -> BotStatsSummary:
    """
    Obtiene resumen completo de estadísticas del bot.

    Incluye:
    - Usuarios (total, nuevos 7d, activos 24h)
    - Uso de comandos (24h, 7d)
    - Top usuarios
    - Rendimiento de API

    Args:
        request: FastAPI request
        db: Database session
        api_key: API key de autenticación

    Returns:
        BotStatsSummary: Estadísticas completas del bot
    """
    users = await stats_service.get_user_stats(db)
    commands = await stats_service.get_command_usage_stats(db)
    top_users = await stats_service.get_top_users(db)
    performance = await stats_service.get_api_performance_stats(db)

    return BotStatsSummary(
        ok=True,
        users=users,
        commands=commands,
        top_users=top_users,
        performance=performance,
        updated_at=datetime.now(timezone.utc),
    )
