"""Service para gestión del sistema de anuncios (ads)."""

import logging
import random
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ad import Ad

logger = logging.getLogger(__name__)


async def create_ad(
    db: AsyncSession,
    text: str,
    is_sponsored: bool = False,
    weight: int = 1,
    created_by: Optional[int] = None,
) -> Optional[Ad]:
    """Crea un anuncio nuevo (activo por defecto)."""
    ad = Ad(
        text=text,
        is_sponsored=is_sponsored,
        weight=weight,
        created_by=created_by,
        is_active=True,
    )
    try:
        db.add(ad)
        await db.commit()
        await db.refresh(ad)
        logger.info("✅ Ad created: id=%d sponsored=%s weight=%d", ad.id, is_sponsored, weight)
        return ad
    except Exception as e:
        logger.error("DB error in create_ad: %s", e, exc_info=True)
        await db.rollback()
        return None


async def list_ads(db: AsyncSession, active_only: bool = False) -> List[Ad]:
    """Lista los anuncios, opcionalmente solo los activos.

    Args:
        db: Sesión de base de datos
        active_only: si True, filtra solo is_active=True

    Returns:
        Lista de Ad ordenada por id ascendente
    """
    stmt = select(Ad)
    if active_only:
        stmt = stmt.where(Ad.is_active.is_(True))
    stmt = stmt.order_by(Ad.id.asc())
    try:
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception as e:
        logger.error("DB error in list_ads: %s", e)
        return []


async def get_ad(db: AsyncSession, ad_id: int) -> Optional[Ad]:
    """Obtiene un anuncio por id."""
    stmt = select(Ad).where(Ad.id == ad_id)
    try:
        result = await db.execute(stmt)
        return result.scalars().first()
    except Exception as e:
        logger.error("DB error in get_ad id=%d: %s", ad_id, e)
        return None


async def get_random_active_ad(db: AsyncSession) -> Optional[Ad]:
    """Elige un anuncio activo al azar, ponderado por 'weight'.

    La tabla de anuncios siempre será pequeña (decenas como mucho), así que
    resolver la ponderación en Python con random.choices es más simple y
    suficientemente eficiente que hacerlo en SQL.

    Returns:
        Ad elegido o None si no hay ninguno activo.
    """
    ads = await list_ads(db, active_only=True)
    if not ads:
        return None
    weights = [max(1, ad.weight) for ad in ads]
    return random.choices(ads, weights=weights, k=1)[0]


async def update_ad(
    db: AsyncSession,
    ad_id: int,
    text: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_sponsored: Optional[bool] = None,
    weight: Optional[int] = None,
) -> Optional[Ad]:
    """Edita campos de un anuncio existente. Solo actualiza los campos != None.

    Returns:
        Ad actualizada, o None si no existe o hubo error.
    """
    ad = await get_ad(db, ad_id)
    if not ad:
        return None
    try:
        if text is not None:
            ad.text = text
        if is_active is not None:
            ad.is_active = is_active
        if is_sponsored is not None:
            ad.is_sponsored = is_sponsored
        if weight is not None:
            ad.weight = weight
        await db.commit()
        await db.refresh(ad)
        logger.info("✏️ Ad updated: id=%d", ad_id)
        return ad
    except Exception as e:
        logger.error("DB error in update_ad id=%d: %s", ad_id, e, exc_info=True)
        await db.rollback()
        return None


async def delete_ad(db: AsyncSession, ad_id: int) -> bool:
    """Elimina un anuncio definitivamente.

    Returns:
        True si se eliminó, False si no existía o hubo error.
    """
    ad = await get_ad(db, ad_id)
    if not ad:
        return False
    try:
        await db.delete(ad)
        await db.commit()
        logger.info("🗑️ Ad deleted: id=%d", ad_id)
        return True
    except Exception as e:
        logger.error("DB error in delete_ad id=%d: %s", ad_id, e, exc_info=True)
        await db.rollback()
        return False


async def count_active(db: AsyncSession) -> int:
    """Cuenta cuántos anuncios están activos."""
    ads = await list_ads(db, active_only=True)
    return len(ads)
