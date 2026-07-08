"""Router para endpoints de estadísticas del bot."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, Request

from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.middleware.auth import require_auth
from src.schemas.stats import (
    BotStatsSummary,
    TrackCommandRequest,
    TrackCommandResponse,
    UserIdsResponse,
    UserLookupData,
    UserLookupResponse,
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


@router.get("/users/ids", response_model=UserIdsResponse)
async def get_all_user_ids(
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_auth),
) -> UserIdsResponse:
    """
    Lista el user_id de TODOS los usuarios registrados del bot.

    Endpoint admin-only (require_auth vía X-API-Key, igual que el resto
    de /api/v1/admin/*). NO es un endpoint público — no exponer nunca
    sin autenticación, es información de usuarios reales.

    Uso exclusivo: taso-bot, comando /ms (broadcast a todos los
    usuarios). Ver docs/plans/2026-07-07-comando-ms-broadcast.md.

    Args:
        db: Database session
        api_key: API key de autenticación (admin)

    Returns:
        UserIdsResponse: lista de user_id (Telegram)
    """
    user_ids = await stats_service.get_all_user_ids(db)
    return UserIdsResponse(ok=True, data=user_ids)


@router.get("/users/lookup", response_model=UserLookupResponse)
async def lookup_user_by_username(
    username: str = Query(..., min_length=1, description="Username a buscar, con o sin @"),
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_auth),
) -> UserLookupResponse:
    """
    Busca el user_id de un usuario registrado a partir de su username.

    Endpoint admin-only (require_auth vía X-API-Key, igual que el resto
    de /api/v1/admin/*). Uso exclusivo: taso-bot, comando /ms <@usuario>
    (mensaje a un único usuario en vez de broadcast). Ver
    docs/plans/2026-07-08-ms-directo-y-tkt-mejoras.md.

    `data` es None si no hay ningún usuario registrado con ese username
    (nunca ejecutó ningún comando del bot, o cambió de username desde
    la última vez que lo hizo).

    Args:
        username: username a buscar (con o sin "@" inicial)
        db: Database session
        api_key: API key de autenticación (admin)

    Returns:
        UserLookupResponse: user_id encontrado, o data=None
    """
    user_id = await stats_service.get_user_id_by_username(db, username)
    if user_id is None:
        return UserLookupResponse(ok=True, data=None)
    return UserLookupResponse(ok=True, data=UserLookupData(user_id=user_id))
