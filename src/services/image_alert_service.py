"""Image alert service for managing user alert preferences."""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.models.image_alert import UserImageAlert


async def get_user_alert(
    db: AsyncSession,
    user_id: int
) -> Optional[UserImageAlert]:
    """
    Obtiene configuración de alerta de un usuario.
    
    Args:
        db: Database session
        user_id: Telegram user_id
    
    Returns:
        UserImageAlert or None
    """
    stmt = select(UserImageAlert).where(UserImageAlert.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalars().first()


async def create_update_alert(
    db: AsyncSession,
    user_id: int,
    alert_time: str = "07:15",
    format_type: str = "photo",
    enabled: bool = True
) -> UserImageAlert:
    """
    Crea o actualiza alerta de usuario.
    
    Args:
        db: Database session
        user_id: Telegram user_id
        alert_time: Time string "HH:MM"
        format_type: "photo" or "document"
        enabled: Whether alert is active
    
    Returns:
        UserImageAlert
    """
    stmt = insert(UserImageAlert).values(
        user_id=user_id,
        alert_time=alert_time,
        format_type=format_type,
        enabled=enabled
    ).on_conflict_do_update(
        index_elements=["user_id"],
        set_=dict(
            alert_time=alert_time,
            format_type=format_type,
            enabled=enabled
        )
    ).returning(UserImageAlert)
    
    result = await db.execute(stmt)
    await db.commit()
    return result.scalars().first()


async def delete_alert(
    db: AsyncSession,
    user_id: int
) -> bool:
    """
    Elimina alerta de usuario.
    
    Args:
        db: Database session
        user_id: Telegram user_id
    
    Returns:
        True if deleted, False if not found
    """
    alert = await get_user_alert(db, user_id)
    if not alert:
        return False
    
    await db.delete(alert)
    await db.commit()
    return True


async def get_all_enabled_alerts(
    db: AsyncSession
) -> List[UserImageAlert]:
    """
    Obtiene todas las alertas activas.
    
    Args:
        db: Database session
    
    Returns:
        List of UserImageAlert
    """
    stmt = select(UserImageAlert).where(UserImageAlert.enabled == True)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def disable_alert(
    db: AsyncSession,
    user_id: int
) -> Optional[UserImageAlert]:
    """
    Desactiva alerta de usuario (sin eliminar).
    
    Args:
        db: Database session
        user_id: Telegram user_id
    
    Returns:
        Updated UserImageAlert or None
    """
    alert = await get_user_alert(db, user_id)
    if not alert:
        return None
    
    alert.enabled = False
    await db.commit()
    await db.refresh(alert)
    return alert
