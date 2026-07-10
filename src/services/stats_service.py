"""Servicio para estadísticas del bot de Telegram."""

from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.bot_stats import BotUser, BotCommandStat
from src.models.api_request_log import ApiRequestLog
from src.schemas.stats import (
    BotUserStats,
    CommandUsageStats,
    CommandUsageItem,
    TopUserStats,
    TopUserItem,
    ApiPerformanceStats,
    ApiUsageStats,
    ApiUsageByClient,
    ApiUsageByEndpoint,
)

# Ventanas soportadas por get_api_usage_stats / api_request_log purge
_WINDOW_TIMEDELTA = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}
API_REQUEST_LOG_RETENTION_DAYS = 30


async def track_command(
    session: AsyncSession,
    command: str,
    user_id: int,
    username: Optional[str] = None,
    source: Optional[str] = None,
    success: bool = True,
) -> None:
    """
    Registra el uso de un comando en la base de datos.

    Args:
        session: SQLAlchemy async session
        command: Nombre del comando ejecutado
        user_id: ID del usuario
        username: Username del usuario (opcional)
        source: Fuente consultada si aplica
        success: Si el comando se ejecutó con éxito
    """
    now = datetime.now(timezone.utc)

    # Actualizar o crear usuario
    user = await session.get(BotUser, user_id)
    if user:
        user.last_seen = now
        user.total_commands += 1
        if username:
            user.username = username
    else:
        user = BotUser(
            user_id=user_id,
            username=username,
            first_seen=now,
            last_seen=now,
            total_commands=1,
        )
        session.add(user)

    # Registrar comando
    stat = BotCommandStat(
        command=command,
        user_id=user_id,
        username=username,
        source=source,
        success=success,
        created_at=now,
    )
    session.add(stat)

    await session.commit()


async def get_user_stats(session: AsyncSession) -> BotUserStats:
    """
    Obtiene estadísticas de usuarios.

    Returns:
        BotUserStats con total, nuevos (7d), activos (24h) y activos
        recientes (15 min — más accionable que 24h para el resumen
        ejecutivo de /status, ver docs/plans/2026-07-08-status-command-v2.md)
    """
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    one_day_ago = now - timedelta(hours=24)
    fifteen_min_ago = now - timedelta(minutes=15)

    # Total usuarios
    total_stmt = select(func.count(BotUser.user_id))
    total = (await session.execute(total_stmt)).scalar() or 0

    # Nuevos últimos 7 días
    new_7d_stmt = select(func.count(BotUser.user_id)).where(
        BotUser.first_seen >= seven_days_ago
    )
    new_7d = (await session.execute(new_7d_stmt)).scalar() or 0

    # Activos últimas 24 horas
    active_24h_stmt = select(func.count(BotUser.user_id)).where(
        BotUser.last_seen >= one_day_ago
    )
    active_24h = (await session.execute(active_24h_stmt)).scalar() or 0

    # Activos últimos 15 minutos
    active_recent_stmt = select(func.count(BotUser.user_id)).where(
        BotUser.last_seen >= fifteen_min_ago
    )
    active_recent = (await session.execute(active_recent_stmt)).scalar() or 0

    return BotUserStats(
        total=total,
        new_7d=new_7d,
        active_24h=active_24h,
        active_recent=active_recent,
    )


async def get_all_user_ids(session: AsyncSession) -> list[int]:
    """
    Obtiene el user_id de TODOS los usuarios registrados en bot_users.

    Uso: comando /ms (broadcast) en taso-bot, vía endpoint admin-only
    GET /api/v1/admin/stats/users/ids. No usar para nada que no sea
    envío masivo desde el propio bot con la admin_key configurada.

    Returns:
        Lista de user_id (int), sin orden garantizado.
    """
    stmt = select(BotUser.user_id)
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


async def get_user_id_by_username(session: AsyncSession, username: str) -> Optional[int]:
    """
    Busca el user_id de un usuario registrado a partir de su username.

    Uso: comando /ms <@usuario> en taso-bot, para enviar un mensaje a un
    único usuario en vez de a todos. Comparación case-insensitive y
    tolerante a que el username venga con o sin "@" al inicio.

    Nota: bot_users.username se actualiza en cada track_command, así que
    puede estar desactualizado si el usuario cambió su username y no
    volvió a interactuar con el bot desde entonces.

    Args:
        session: SQLAlchemy async session
        username: Username a buscar (con o sin "@" inicial)

    Returns:
        user_id (int) si se encuentra, None si no hay match.
    """
    clean_username = username.lstrip("@").strip().lower()
    if not clean_username:
        return None

    stmt = select(BotUser.user_id).where(
        func.lower(BotUser.username) == clean_username
    )
    result = await session.execute(stmt)
    row = result.first()
    return row[0] if row else None


async def get_command_usage_stats(session: AsyncSession) -> CommandUsageStats:
    """
    Obtiene estadísticas de uso de comandos.

    Returns:
        CommandUsageStats con comandos de 24h, 7d y 30d
    """
    now = datetime.now(timezone.utc)
    one_day_ago = now - timedelta(hours=24)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # Comandos 24h
    stmt_24h = (
        select(BotCommandStat.command, func.count(BotCommandStat.id).label("count"))
        .where(BotCommandStat.created_at >= one_day_ago)
        .group_by(BotCommandStat.command)
        .order_by(func.count(BotCommandStat.id).desc())
    )
    result_24h = await session.execute(stmt_24h)
    commands_24h = [
        CommandUsageItem(command=row.command, count=row.count)
        for row in result_24h.all()
    ]

    # Comandos 7d
    stmt_7d = (
        select(BotCommandStat.command, func.count(BotCommandStat.id).label("count"))
        .where(BotCommandStat.created_at >= seven_days_ago)
        .group_by(BotCommandStat.command)
        .order_by(func.count(BotCommandStat.id).desc())
    )
    result_7d = await session.execute(stmt_7d)
    commands_7d = [
        CommandUsageItem(command=row.command, count=row.count)
        for row in result_7d.all()
    ]

    # Comandos 30d
    stmt_30d = (
        select(BotCommandStat.command, func.count(BotCommandStat.id).label("count"))
        .where(BotCommandStat.created_at >= thirty_days_ago)
        .group_by(BotCommandStat.command)
        .order_by(func.count(BotCommandStat.id).desc())
    )
    result_30d = await session.execute(stmt_30d)
    commands_30d = [
        CommandUsageItem(command=row.command, count=row.count)
        for row in result_30d.all()
    ]

    return CommandUsageStats(
        commands_24h=commands_24h,
        commands_7d=commands_7d,
        commands_30d=commands_30d,
    )


async def get_top_users(session: AsyncSession, limit: int = 10) -> TopUserStats:
    """
    Obtiene los top usuarios por cantidad de comandos.

    Args:
        session: SQLAlchemy async session
        limit: Cantidad de usuarios a retornar

    Returns:
        TopUserStats con los top usuarios
    """
    stmt = (
        select(BotUser.user_id, BotUser.username, BotUser.total_commands)
        .order_by(BotUser.total_commands.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    top_users = [
        TopUserItem(user_id=row.user_id, username=row.username, total_commands=row.total_commands)
        for row in result.all()
    ]

    return TopUserStats(top_users=top_users)


async def get_api_performance_stats(session: AsyncSession) -> ApiPerformanceStats:
    """
    Obtiene estadísticas de rendimiento de la API.

    success_rate/total_requests_24h siguen viniendo de bot_command_stats
    (uso reportado por el bot). avg_response_ms ahora se calcula desde
    api_request_log (todas las requests HTTP reales capturadas por el
    middleware track_requests en main.py), reemplazando el placeholder
    fijo en 0.0 que existía antes. Ver
    docs/plans/2026-07-08-status-command-v2.md (Fase 1).

    Returns:
        ApiPerformanceStats con métricas de rendimiento
    """
    now = datetime.now(timezone.utc)
    one_day_ago = now - timedelta(hours=24)

    # Total requests 24h (comandos del bot)
    total_stmt = select(func.count(BotCommandStat.id)).where(
        BotCommandStat.created_at >= one_day_ago
    )
    total_requests = (await session.execute(total_stmt)).scalar() or 0

    # Success rate
    success_stmt = select(func.count(BotCommandStat.id)).where(
        and_(
            BotCommandStat.created_at >= one_day_ago,
            BotCommandStat.success == True,
        )
    )
    success_count = (await session.execute(success_stmt)).scalar() or 0

    success_rate = (success_count / total_requests * 100) if total_requests > 0 else 100.0

    # Avg response time real, desde api_request_log (todas las fuentes)
    avg_stmt = select(func.avg(ApiRequestLog.duration_ms)).where(
        ApiRequestLog.created_at >= one_day_ago
    )
    avg_response_ms = (await session.execute(avg_stmt)).scalar() or 0.0

    return ApiPerformanceStats(
        success_rate=success_rate,
        avg_response_ms=float(avg_response_ms),
        total_requests_24h=total_requests,
    )


async def log_api_request(
    session: AsyncSession,
    method: str,
    path: str,
    status_code: int,
    duration_ms: int,
    client_id: Optional[str] = None,
) -> None:
    """
    Registra una request HTTP individual en api_request_log.

    Llamado desde el middleware track_requests (main.py) de forma
    fire-and-forget — si falla, no debe afectar la respuesta al cliente.

    Args:
        session: SQLAlchemy async session (propia, no la del request)
        method: Método HTTP (GET, POST, etc.)
        path: Path del endpoint solicitado
        status_code: Código de respuesta HTTP
        duration_ms: Duración de la request en milisegundos
        client_id: Identificador del cliente (bot/app/ext/extmf/web/unknown)
    """
    entry = ApiRequestLog(
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=duration_ms,
        client_id=client_id,
        created_at=datetime.now(timezone.utc),
    )
    session.add(entry)
    await session.commit()


async def get_api_usage_stats(session: AsyncSession, window: str = "24h") -> ApiUsageStats:
    """
    Obtiene el uso de la API pública desglosado por cliente y por endpoint.

    Fuente: api_request_log (todas las requests HTTP reales, capturadas
    por el middleware track_requests), no solo lo reportado por el bot.
    Uso: comando /status → botón "🌐 API pública".

    Args:
        session: SQLAlchemy async session
        window: Ventana de tiempo — "24h" | "7d" | "30d" (default "24h")

    Returns:
        ApiUsageStats con totales, desglose por cliente y top 10 endpoints
    """
    delta = _WINDOW_TIMEDELTA.get(window, _WINDOW_TIMEDELTA["24h"])
    since = datetime.now(timezone.utc) - delta

    # Totales de la ventana
    total_stmt = select(func.count(ApiRequestLog.id)).where(ApiRequestLog.created_at >= since)
    total_requests = (await session.execute(total_stmt)).scalar() or 0

    errors_stmt = select(func.count(ApiRequestLog.id)).where(
        and_(ApiRequestLog.created_at >= since, ApiRequestLog.status_code >= 400)
    )
    total_errors = (await session.execute(errors_stmt)).scalar() or 0

    avg_stmt = select(func.avg(ApiRequestLog.duration_ms)).where(ApiRequestLog.created_at >= since)
    avg_duration_ms = (await session.execute(avg_stmt)).scalar() or 0.0

    error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0.0

    # Desglose por cliente
    client_stmt = (
        select(
            ApiRequestLog.client_id,
            func.count(ApiRequestLog.id).label("requests"),
            func.sum(case((ApiRequestLog.status_code >= 400, 1), else_=0)).label("errors"),
            func.avg(ApiRequestLog.duration_ms).label("avg_duration_ms"),
        )
        .where(ApiRequestLog.created_at >= since)
        .group_by(ApiRequestLog.client_id)
        .order_by(func.count(ApiRequestLog.id).desc())
    )
    client_rows = (await session.execute(client_stmt)).all()
    by_client = [
        ApiUsageByClient(
            client_id=row.client_id or "unknown",
            requests=row.requests,
            errors=int(row.errors or 0),
            avg_duration_ms=float(row.avg_duration_ms or 0.0),
        )
        for row in client_rows
    ]

    # Top 10 endpoints por volumen
    endpoint_stmt = (
        select(
            ApiRequestLog.path,
            func.count(ApiRequestLog.id).label("requests"),
            func.sum(case((ApiRequestLog.status_code >= 400, 1), else_=0)).label("errors"),
            func.avg(ApiRequestLog.duration_ms).label("avg_duration_ms"),
        )
        .where(ApiRequestLog.created_at >= since)
        .group_by(ApiRequestLog.path)
        .order_by(func.count(ApiRequestLog.id).desc())
        .limit(10)
    )
    endpoint_rows = (await session.execute(endpoint_stmt)).all()
    by_endpoint = [
        ApiUsageByEndpoint(
            path=row.path,
            requests=row.requests,
            errors=int(row.errors or 0),
            avg_duration_ms=float(row.avg_duration_ms or 0.0),
        )
        for row in endpoint_rows
    ]

    return ApiUsageStats(
        window=window,
        total_requests=total_requests,
        total_errors=total_errors,
        error_rate=error_rate,
        avg_duration_ms=float(avg_duration_ms),
        by_client=by_client,
        by_endpoint=by_endpoint,
        updated_at=datetime.now(timezone.utc),
    )


async def purge_old_api_request_logs(session: AsyncSession) -> int:
    """
    Elimina filas de api_request_log más viejas que API_REQUEST_LOG_RETENTION_DAYS.

    Llamado desde el job refresh_all (scheduler.py) — mismo criterio ya
    aplicado a rate_snapshots (ver snapshot-cleanup-retention-plan).

    Returns:
        Cantidad de filas eliminadas.
    """
    from sqlalchemy import delete

    cutoff = datetime.now(timezone.utc) - timedelta(days=API_REQUEST_LOG_RETENTION_DAYS)
    stmt = delete(ApiRequestLog).where(ApiRequestLog.created_at < cutoff)
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or 0
