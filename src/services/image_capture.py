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

logger = logging.getLogger(__name__)


# Configuration
IMAGE_STORAGE_PATH = "/home/ersus/tasalo/taso-api/static/images/eltoque"


def get_storage_path() -> str:
    """Get the image storage path, checking for environment variable override."""
    return os.environ.get("TASALO_IMAGE_STORAGE_PATH", IMAGE_STORAGE_PATH)


async def capture_and_store_image(
    db: AsyncSession,
    source: str = "eltoque"
) -> Dict:
    """
    Captura imagen y la almacena en filesystem + DB.
    
    Args:
        db: Database session
        source: Source name ("eltoque")
    
    Returns:
        dict: {success: bool, image: Optional[ImageSnapshot], error: Optional[str]}
    """
    try:
        storage_path = get_storage_path()
        
        # Asegurar directorio existe
        ensure_directory_exists(f"{storage_path}/placeholder.jpg")
        
        # Generar filename con timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{source}_{timestamp}.jpg"
        output_path = os.path.join(storage_path, filename)
        
        # Capturar imagen
        result = await capture_eltoque_image(output_path)
        
        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Unknown error")
            }
        
        # Crear snapshot en DB
        snapshot = ImageSnapshot(
            source=source,
            image_path=output_path,
            file_size=result["file_size"],
            extra_data=json.dumps({
                "width": result["width"],
                "height": result["height"],
                "url": "https://iframe.cubanomic.com/"
            })
        )
        
        db.add(snapshot)
        await db.commit()
        await db.refresh(snapshot)
        
        return {
            "success": True,
            "image": snapshot
        }
        
    except Exception as e:
        await db.rollback()
        return {
            "success": False,
            "error": str(e)
        }


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
