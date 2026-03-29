"""Router for image endpoints."""

import json
import logging
import os
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

logger = logging.getLogger(__name__)

from src.database import get_db
from src.services.image_capture import capture_and_store_image, get_latest_image, get_image_by_date
from src.services.image_alert_service import (
    get_user_alert,
    create_update_alert,
    delete_alert,
    get_all_enabled_alerts,
    disable_alert
)
from src.schemas.image import (
    ImageSnapshotSchema,
    UserImageAlertSchema,
    AlertCreateSchema,
    APIResponse
)

router = APIRouter(prefix="/api/v1/images", tags=["Images"])


@router.post("/eltoque/capture", response_model=APIResponse)
async def capture_eltoque_image_endpoint(
    db: AsyncSession = Depends(get_db)
):
    """
    Capturar imagen de ElToque manualmente (on-demand).
    """
    result = await capture_and_store_image(db, source="eltoque")
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return APIResponse(
        ok=True,
        data=ImageSnapshotSchema.model_validate(result["image"]),
        count=1
    )


@router.get("/eltoque/latest", response_model=APIResponse)
async def get_latest_eltoque_image(
    db: AsyncSession = Depends(get_db)
):
    """
    Obtener última imagen capturada de ElToque.
    """
    image = await get_latest_image(db, source="eltoque")
    
    if not image:
        raise HTTPException(status_code=404, detail="No images found")
    
    return APIResponse(
        ok=True,
        data=ImageSnapshotSchema.model_validate(image),
        count=1
    )


@router.get("/eltoque/{date}", response_model=APIResponse)
async def get_eltoque_image_by_date(
    date: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Obtener imagen de ElToque por fecha (YYYY-MM-DD).
    """
    image = await get_image_by_date(db, source="eltoque", date=date)
    
    if not image:
        raise HTTPException(status_code=404, detail=f"No image found for date {date}")
    
    return APIResponse(
        ok=True,
        data=ImageSnapshotSchema.model_validate(image),
        count=1
    )


@router.get("/eltoque/file/latest")
async def get_latest_eltoque_file(
    db: AsyncSession = Depends(get_db)
):
    """
    Descargar archivo de última imagen de ElToque.
    """
    image = await get_latest_image(db, source="eltoque")
    
    if not image or not os.path.exists(image.image_path):
        raise HTTPException(status_code=404, detail="Image file not found")
    
    return FileResponse(
        image.image_path,
        media_type="image/jpeg",
        filename=os.path.basename(image.image_path)
    )


@router.get("/alerts/{user_id}", response_model=APIResponse)
async def get_user_alert_endpoint(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Obtener configuración de alerta de un usuario.
    """
    alert = await get_user_alert(db, user_id)
    
    if not alert:
        return APIResponse(
            ok=True,
            data=None,
            count=0
        )
    
    return APIResponse(
        ok=True,
        data=UserImageAlertSchema.model_validate(alert),
        count=1
    )


@router.post("/alerts", response_model=APIResponse)
async def create_update_alert_endpoint(
    alert_data: AlertCreateSchema,
    db: AsyncSession = Depends(get_db)
):
    """
    Crear o actualizar alerta de usuario.
    """
    try:
        logger.info(f"Creating alert: user_id={alert_data.user_id}, time={alert_data.alert_time}")
        
        alert = await create_update_alert(
            db,
            user_id=alert_data.user_id,
            alert_time=alert_data.alert_time,
            format_type=alert_data.format_type,
            enabled=alert_data.enabled
        )

        logger.info(f"Alert created successfully: {alert}")

        return APIResponse(
            ok=True,
            data=UserImageAlertSchema.model_validate(alert),
            count=1
        )
    except Exception as e:
        logger.error(f"Error creating alert: {e}", exc_info=True)
        raise


@router.delete("/alerts/{user_id}", response_model=APIResponse)
async def delete_alert_endpoint(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Eliminar alerta de usuario.
    """
    deleted = await delete_alert(db, user_id=user_id)
    
    return APIResponse(
        ok=True,
        data={"deleted": deleted},
        count=1
    )


@router.get("/alerts", response_model=APIResponse)
async def get_all_enabled_alerts_endpoint(
    enabled: bool = Query(default=True),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtener todas las alertas activas.
    """
    if enabled:
        alerts = await get_all_enabled_alerts(db)
    else:
        alerts = []
    
    return APIResponse(
        ok=True,
        data=[UserImageAlertSchema.model_validate(a) for a in alerts],
        count=len(alerts)
    )


@router.post("/alerts/{user_id}/disable", response_model=APIResponse)
async def disable_alert_endpoint(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Desactivar alerta de usuario (sin eliminar).
    """
    alert = await disable_alert(db, user_id=user_id)
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    return APIResponse(
        ok=True,
        data=UserImageAlertSchema.model_validate(alert),
        count=1
    )
