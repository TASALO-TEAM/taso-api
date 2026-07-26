"""Tspl service: subscription CRUD para el envío programado de /tspl.

Hasta 2 horarios (UTC) por usuario — a diferencia de year_service, que
solo guarda uno. Ver docs/plans/2026-07-24-tspl-suscripcion-horarios.md
"""

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tspl_subscription import TsplSubscription
from src.schemas.tspl import TsplSubscriptionResponse, TsplSubscriptionListResponse

logger = logging.getLogger(__name__)

MAX_SUBSCRIPTIONS_PER_USER = 2


async def get_my_subscriptions(db: AsyncSession, user_id: int) -> list[TsplSubscription]:
    """Retorna las filas de suscripción del usuario (0, 1 o 2), ordenadas por hora."""
    result = await db.execute(
        select(TsplSubscription)
        .where(TsplSubscription.user_id == user_id)
        .order_by(TsplSubscription.hour)
    )
    return list(result.scalars().all())


async def add_my_subscription(db: AsyncSession, user_id: int, hour: int) -> TsplSubscription:
    """Agrega un horario para el usuario.

    - Si ya existe una fila con esa hora exacta, la retorna tal cual
      (idempotente — no es un error pedir de nuevo la misma hora).
    - Si el usuario ya tiene MAX_SUBSCRIPTIONS_PER_USER horas distintas,
      lanza ValueError("max_subscriptions_reached") — el router lo
      traduce a HTTP 409.

    Returns:
        La fila de suscripción (nueva o existente).
    """
    existing_rows = await get_my_subscriptions(db, user_id)

    for row in existing_rows:
        if row.hour == hour:
            return row

    if len(existing_rows) >= MAX_SUBSCRIPTIONS_PER_USER:
        raise ValueError("max_subscriptions_reached")

    new_sub = TsplSubscription(user_id=user_id, hour=hour)
    db.add(new_sub)
    await db.commit()
    await db.refresh(new_sub)
    logger.info("✅ /tspl subscription added: user=%d hour=%d", user_id, hour)
    return new_sub


async def delete_my_subscription(db: AsyncSession, user_id: int, hour: int) -> bool:
    """Borra un horario puntual del usuario. Retorna True si borró algo."""
    result = await db.execute(
        select(TsplSubscription).where(
            TsplSubscription.user_id == user_id,
            TsplSubscription.hour == hour,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        return False
    await db.delete(row)
    await db.commit()
    logger.info("🗑 /tspl subscription removed: user=%d hour=%d", user_id, hour)
    return True


async def delete_all_my_subscriptions(db: AsyncSession, user_id: int) -> int:
    """Borra TODOS los horarios del usuario. Retorna cuántos borró."""
    rows = await get_my_subscriptions(db, user_id)
    for row in rows:
        await db.delete(row)
    if rows:
        await db.commit()
        logger.info("🗑 Todas las /tspl subscriptions removidas: user=%d (%d filas)", user_id, len(rows))
    return len(rows)


async def get_all_subscriptions(db: AsyncSession) -> TsplSubscriptionListResponse:
    """Lista TODAS las suscripciones de todos los usuarios (para el dispatcher)."""
    result = await db.execute(select(TsplSubscription).order_by(TsplSubscription.id))
    rows = result.scalars().all()
    return TsplSubscriptionListResponse(
        ok=True,
        data=[
            TsplSubscriptionResponse(
                id=r.id, user_id=r.user_id, hour=r.hour, created_at=r.created_at,
            )
            for r in rows
        ],
        count=len(rows),
    )
