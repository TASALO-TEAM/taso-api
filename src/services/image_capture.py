"""Image capture service for managing screenshot operations."""

import json
import os
from datetime import datetime, timezone
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.image_snapshot import ImageSnapshot
from src.scrapers.images import capture_eltoque_image, ensure_directory_exists


# Configuration
IMAGE_STORAGE_PATH = "/home/ersus/tasalo/taso-api/static/images/eltoque"


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
        # Asegurar directorio existe
        ensure_directory_exists(f"{IMAGE_STORAGE_PATH}/placeholder.jpg")
        
        # Generar filename con timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{source}_{timestamp}.jpg"
        output_path = os.path.join(IMAGE_STORAGE_PATH, filename)
        
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
    
    result = await db.execute(stmt)
    return result.scalars().first()


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
    
    result = await db.execute(stmt)
    return result.scalars().first()
