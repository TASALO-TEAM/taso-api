"""Service para gestión de alertas de precio de criptomonedas."""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, delete, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.price_alert import PriceAlert

logger = logging.getLogger(__name__)


async def create_alert(
    db: AsyncSession,
    user_id: int,
    coin: str,
    target_price: float,
    condition: str,
) -> Optional[PriceAlert]:
    """
    Crea una alerta de precio individual (ABOVE o BELOW).

    Args:
        db: Sesión de base de datos
        user_id: Telegram user_id
        coin: Símbolo de la moneda (ej: "BTC")
        target_price: Precio objetivo
        condition: "ABOVE" o "BELOW"

    Returns:
        PriceAlert creada o None si hubo error
    """
    alert = PriceAlert(
        user_id=user_id,
        coin=coin.upper(),
        target_price=target_price,
        condition=condition,
        status="ACTIVE",
    )
    try:
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        logger.info(
            "✅ Alert created: user=%d coin=%s %s %.6f (id=%d)",
            user_id, coin, condition, target_price, alert.id,
        )
        return alert
    except Exception as e:
        logger.error("DB error in create_alert: %s", e, exc_info=True)
        await db.rollback()
        return None


async def get_user_alerts(
    db: AsyncSession,
    user_id: int,
    status: str = "ACTIVE",
) -> List[PriceAlert]:
    """
    Obtiene las alertas de un usuario filtradas por estado.

    Args:
        db: Sesión de base de datos
        user_id: Telegram user_id
        status: "ACTIVE" | "TRIGGERED" | "ALL"

    Returns:
        Lista de PriceAlert
    """
    stmt = select(PriceAlert).where(PriceAlert.user_id == user_id)
    if status != "ALL":
        stmt = stmt.where(PriceAlert.status == status)
    stmt = stmt.order_by(PriceAlert.created_at.desc())
    try:
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception as e:
        logger.error("DB error in get_user_alerts user=%d: %s", user_id, e)
        return []


async def delete_alert(
    db: AsyncSession,
    alert_id: int,
    user_id: int,
) -> bool:
    """
    Elimina una alerta específica (verifica que pertenezca al usuario).

    Args:
        db: Sesión de base de datos
        alert_id: ID de la alerta
        user_id: Telegram user_id (seguridad: solo puede borrar las propias)

    Returns:
        True si se eliminó, False si no existía o no pertenece al usuario
    """
    stmt = select(PriceAlert).where(
        PriceAlert.id == alert_id,
        PriceAlert.user_id == user_id,
    )
    try:
        result = await db.execute(stmt)
        alert = result.scalars().first()
        if not alert:
            return False
        await db.delete(alert)
        await db.commit()
        logger.info("🗑️ Alert deleted: id=%d user=%d", alert_id, user_id)
        return True
    except Exception as e:
        logger.error("DB error in delete_alert id=%d: %s", alert_id, e, exc_info=True)
        await db.rollback()
        return False


async def delete_all_user_alerts(
    db: AsyncSession,
    user_id: int,
) -> int:
    """
    Elimina todas las alertas de un usuario.

    Returns:
        Número de alertas eliminadas
    """
    stmt = delete(PriceAlert).where(PriceAlert.user_id == user_id)
    try:
        result = await db.execute(stmt)
        await db.commit()
        count = result.rowcount
        logger.info("🗑️ All alerts deleted for user=%d (count=%d)", user_id, count)
        return count
    except Exception as e:
        logger.error("DB error in delete_all_user_alerts user=%d: %s", user_id, e, exc_info=True)
        await db.rollback()
        return 0


async def mark_triggered(
    db: AsyncSession,
    alert_id: int,
) -> Optional[PriceAlert]:
    """
    Marca una alerta como TRIGGERED con timestamp.

    Args:
        db: Sesión de base de datos
        alert_id: ID de la alerta

    Returns:
        PriceAlert actualizada o None
    """
    stmt = select(PriceAlert).where(PriceAlert.id == alert_id)
    try:
        result = await db.execute(stmt)
        alert = result.scalars().first()
        if not alert:
            return None
        alert.status = "TRIGGERED"
        alert.triggered_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(alert)
        logger.info("🔔 Alert triggered: id=%d user=%d coin=%s", alert_id, alert.user_id, alert.coin)
        return alert
    except Exception as e:
        logger.error("DB error in mark_triggered id=%d: %s", alert_id, e, exc_info=True)
        await db.rollback()
        return None


async def get_active_coins(db: AsyncSession) -> List[str]:
    """
    Retorna la lista de coins únicas que tienen al menos una alerta ACTIVE.
    Usada por el checker del bot para saber qué monedas consultar.

    Returns:
        Lista de símbolos en mayúsculas, ej: ["BTC", "ETH", "HIVE"]
    """
    stmt = select(distinct(PriceAlert.coin)).where(PriceAlert.status == "ACTIVE")
    try:
        result = await db.execute(stmt)
        coins = [row[0] for row in result.all()]
        return coins
    except Exception as e:
        logger.error("DB error in get_active_coins: %s", e)
        return []


async def get_active_alerts_for_coins(
    db: AsyncSession,
    coins: List[str],
) -> List[PriceAlert]:
    """
    Obtiene todas las alertas ACTIVE para una lista de coins.
    Usada por el checker para evaluar condiciones de disparo.

    Args:
        db: Sesión de base de datos
        coins: Lista de símbolos a consultar

    Returns:
        Lista de PriceAlert activas
    """
    if not coins:
        return []
    stmt = (
        select(PriceAlert)
        .where(PriceAlert.status == "ACTIVE")
        .where(PriceAlert.coin.in_([c.upper() for c in coins]))
    )
    try:
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception as e:
        logger.error("DB error in get_active_alerts_for_coins: %s", e)
        return []
