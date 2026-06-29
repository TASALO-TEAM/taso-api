"""Image capture service for managing screenshot operations."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, cast, Date
from sqlalchemy.exc import SQLAlchemyError

from src.models.image_snapshot import ImageSnapshot
from src.scrapers.images import capture_eltoque_image, ensure_directory_exists
from src.scrapers.eltoque import fetch_eltoque
from src.services.image_generator import generate_toque_image

logger = logging.getLogger(__name__)

IMAGE_STORAGE_PATH = "/home/ersus/tasalo/taso-api/static/images/eltoque"


def get_storage_path() -> str:
    return os.environ.get("TASALO_IMAGE_STORAGE_PATH", IMAGE_STORAGE_PATH)


async def capture_and_store_image(
    db: AsyncSession,
    source: str = "eltoque",
    force: bool = False,
) -> Dict:
    """
    Captura imagen y la almacena en filesystem + DB.

    Si ya existe una imagen de hoy y force=False, devuelve la existente
    sin generar nada (cero consumo de CPU/memoria).

    Estrategia:
      1. Si hay imagen de hoy en DB → devolver sin generar (a menos que force=True)
      2. Intentar captura con Playwright/Selenium (fiel al iframe original)
      3. Si falla → generar con Pillow usando datos de tasas.eltoque.com
      4. Guardar en filesystem + DB

    Args:
        db: Database session
        source: Source name ("eltoque")
        force: Forzar regeneración aunque ya exista imagen de hoy
    """
    # ── Paso 1: devolver imagen existente de hoy si existe ───────────────────
    if not force:
        existing = await get_today_image(db, source)
        if existing and os.path.exists(existing.image_path):
            logger.info("♻️ [capture] Imagen de hoy ya existe, devolviendo sin generar")
            return {"success": True, "image": existing, "cached": True}

    storage_path = get_storage_path()
    os.makedirs(storage_path, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{source}_{timestamp}.png"
    output_path = os.path.join(storage_path, filename)

    # ── Paso 2: intentar captura con browser ─────────────────────────────────
    capture_result = await capture_eltoque_image(output_path)

    if capture_result.get("success"):
        logger.info("✅ [capture] Imagen capturada con browser: %s", output_path)
        return await _save_snapshot(db, source, output_path, capture_result)

    logger.warning(
        "⚠️ [capture] Browser falló (%s), usando generador Pillow...",
        capture_result.get("error", "unknown"),
    )

    # ── Paso 3: fallback — generar con Pillow ────────────────────────────────
    rates_data = await fetch_eltoque()
    if not rates_data:
        return {"success": False, "error": "No se pudieron obtener datos de ElToque para generar imagen"}

    img_bytes = generate_toque_image(rates_data)
    if not img_bytes:
        return {"success": False, "error": "Fallo al generar imagen con Pillow"}

    with open(output_path, "wb") as f:
        f.write(img_bytes)

    file_size = os.path.getsize(output_path)
    logger.info("✅ [capture] Imagen generada con Pillow: %s (%d bytes)", output_path, file_size)

    return await _save_snapshot(
        db, source, output_path,
        {"file_size": file_size, "width": 800, "height": None, "generated": True}
    )


async def _save_snapshot(
    db: AsyncSession,
    source: str,
    output_path: str,
    result: dict,
) -> dict:
    """Guarda el registro de la imagen en la DB."""
    try:
        snapshot = ImageSnapshot(
            source=source,
            image_path=output_path,
            file_size=result.get("file_size", 0),
            extra_data=json.dumps({
                "width": result.get("width"),
                "height": result.get("height"),
                "generated": result.get("generated", False),
                "url": "https://iframe.cubanomic.com/",
            }),
        )
        db.add(snapshot)
        await db.commit()
        await db.refresh(snapshot)
        return {"success": True, "image": snapshot, "cached": False}
    except Exception as e:
        await db.rollback()
        logger.error("❌ [capture] Error guardando snapshot en DB: %s", e)
        return {"success": False, "error": str(e)}


async def get_latest_image(
    db: AsyncSession,
    source: str = "eltoque"
) -> Optional[ImageSnapshot]:
    """
    Obtiene la última imagen capturada para una fuente.
    
    Args:
        db: Database session
        source: Source name
    
    Returns:
        ImageSnapshot or None
    """
    stmt = (
        select(ImageSnapshot)
        .where(ImageSnapshot.source == source)
        .order_by(ImageSnapshot.captured_at.desc())
        .limit(1)
    )
    
    try:
        result = await db.execute(stmt)
        return result.scalars().first()
    except Exception as e:
        logger.error(f"DB error in get_latest_image for {source}: {e}")
        return None


async def get_today_image(
    db: AsyncSession,
    source: str = "eltoque"
) -> Optional[ImageSnapshot]:
    """
    Obtiene la imagen del día actual para una fuente.
    Si no hay imagen del día, devuelve None.
    
    Args:
        db: Database session
        source: Source name
    
    Returns:
        ImageSnapshot or None
    """
    today = datetime.now(timezone.utc).date()
    
    stmt = (
        select(ImageSnapshot)
        .where(ImageSnapshot.source == source)
        .where(func.date(ImageSnapshot.captured_at) == today)
        .order_by(ImageSnapshot.captured_at.desc())
        .limit(1)
    )
    
    try:
        result = await db.execute(stmt)
        return result.scalars().first()
    except Exception as e:
        logger.error(f"DB error in get_today_image for {source}: {e}")
        return None


async def get_image_by_date(
    db: AsyncSession,
    source: str,
    date: str  # Format: "YYYY-MM-DD"
) -> Optional[ImageSnapshot]:
    """
    Obtiene imagen de una fecha específica.
    
    Args:
        db: Database session
        source: Source name
        date: Date string "YYYY-MM-DD"
    
    Returns:
        ImageSnapshot or None
    """
    from sqlalchemy import func, cast, Date
    
    stmt = (
        select(ImageSnapshot)
        .where(ImageSnapshot.source == source)
        .where(
            cast(ImageSnapshot.captured_at, Date) == date
        )
        .order_by(ImageSnapshot.captured_at.desc())
        .limit(1)
    )
    
    try:
        result = await db.execute(stmt)
        return result.scalars().first()
    except Exception as e:
        logger.error(f"DB error in get_image_by_date for {source} date={date}: {e}")
        return None
