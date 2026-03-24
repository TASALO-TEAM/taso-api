"""Servicio para estadísticas del bot de Telegram."""

from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.bot_stats import BotUser, BotCommandStat
from src.schemas.stats import (
    BotUserStats,
    CommandUsageStats,
    CommandUsageItem,
    TopUserStats,
    TopUserItem,
    ApiPerformanceStats,
)


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
        BotUserStats con total, nuevos (7d) y activos (24h)
    """
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    one_day_ago = now - timedelta(hours=24)

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

    return BotUserStats(
        total=total,
        new_7d=new_7d,
        active_24h=active_24h,
    )


async def get_command_usage_stats(session: AsyncSession) -> CommandUsageStats:
    """
    Obtiene estadísticas de uso de comandos.

    Returns:
        CommandUsageStats con comandos de 24h y 7d
    """
    now = datetime.now(timezone.utc)
    one_day_ago = now - timedelta(hours=24)
    seven_days_ago = now - timedelta(days=7)

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

    return CommandUsageStats(
        commands_24h=commands_24h,
        commands_7d=commands_7d,
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

    Nota: Por ahora retorna valores estimados. Se puede mejorar
    implementando logging de response times en un middleware.

    Returns:
        ApiPerformanceStats con métricas de rendimiento
    """
    now = datetime.now(timezone.utc)
    one_day_ago = now - timedelta(hours=24)

    # Total requests 24h
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

    # Avg response time (placeholder - se puede implementar con middleware)
    avg_response_ms = 0.0

    return ApiPerformanceStats(
        success_rate=success_rate,
        avg_response_ms=avg_response_ms,
        total_requests_24h=total_requests,
    )
