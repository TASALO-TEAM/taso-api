"""Image capture service — gestiona la imagen única del post de ElToque.

Modelo (2026-06-30): archivo canónico único, sobrescrito en cada intento.
Una sola fila en DB (upsert), sin historial por fecha. Si la descarga falla,
se sirve el archivo/fila existente marcados como 'stale'.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.image_snapshot import ImageSnapshot
from src.scrapers.images import download_eltoque_post_image, ensure_directory_exists

logger = logging.getLogger(__name__)

IMAGE_STORAGE_PATH = "/home/ersus/tasalo/taso-api/static/images/eltoque"
CANONICAL_FILENAME = "eltoque_post.png"


def get_storage_path() -> str:
    return os.environ.get("TASALO_IMAGE_STORAGE_PATH", IMAGE_STORAGE_PATH)


def get_canonical_path() -> str:
    return os.path.join(get_storage_path(), CANONICAL_FILENAME)


async def capture_and_store_image(
    db: AsyncSession,
    source: str = "eltoque",
) -> Dict:
    """
    Intenta refrescar la imagen del post (siempre, bajo demanda) y la
    almacena en un path canónico único + una sola fila en DB.

    Estrategia:
      1. Intentar descarga fresca haciendo clic en 'Guardar POST'
      2. Éxito → sobrescribir archivo canónico, upsert de la fila en DB
      3. Fallo → si existe archivo/fila previa, devolverla marcada 'stale'
      4. Fallo total (sin nada previo) → error real

    Args:
        db: Database session
        source: Source name ("eltoque")
    """
    output_path = get_canonical_path()
    await ensure_directory_exists(output_path)

    download_result = await download_eltoque_post_image(output_path)

    if download_result.get("success"):
        logger.info("✅ [capture] Imagen refrescada: %s", output_path)
        return await _upsert_snapshot(db, source, output_path, download_result)

    logger.warning(
        "⚠️ [capture] Descarga falló (%s), evaluando fallback local...",
        download_result.get("error", "unknown"),
    )

    existing = await get_latest_image(db, source)
    if existing and os.path.exists(existing.image_path):
        logger.info("♻️ [capture] Sirviendo imagen local existente (stale)")
        return {
            "success": True,
            "image": existing,
            "cached": True,
            "stale": True,
            "error": download_result.get("error"),
        }

    return {
        "success": False,
        "error": download_result.get("error", "Descarga falló y no hay imagen local previa"),
    }


async def _upsert_snapshot(
    db: AsyncSession,
    source: str,
    output_path: str,
    result: dict,
) -> dict:
    """Crea o actualiza la única fila de ImageSnapshot para esta fuente."""
    try:
        existing = await get_latest_image(db, source)
        extra_data = json.dumps({
            "url": "https://iframe.cubanomic.com/",
            "method": "download_guardar_post",
        })

        if existing:
            existing.image_path = output_path
            existing.file_size = result.get("file_size", 0)
            existing.captured_at = datetime.now(timezone.utc)
            existing.extra_data = extra_data
            snapshot = existing
        else:
            snapshot = ImageSnapshot(
                source=source,
                image_path=output_path,
                file_size=result.get("file_size", 0),
                extra_data=extra_data,
            )
            db.add(snapshot)

        await db.commit()
        await db.refresh(snapshot)
        return {"success": True, "image": snapshot, "cached": False, "stale": False}
    except Exception as e:
        await db.rollback()
        logger.error("❌ [capture] Error guardando snapshot en DB: %s", e)
        return {"success": False, "error": str(e)}


async def get_latest_image(
    db: AsyncSession,
    source: str = "eltoque"
) -> Optional[ImageSnapshot]:
    """
    Obtiene la (única) imagen actual para una fuente.

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
