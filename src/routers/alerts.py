"""Router para endpoints de alertas de precio de criptomonedas.

Todos los endpoints requieren autenticación con X-API-Key.
Las extensiones de navegador (taso-ext, taso-extmf) nunca consumen estos endpoints.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.middleware.auth import require_auth
from src.services.price_alert_service import (
    create_alert,
    get_user_alerts,
    delete_alert,
    delete_all_user_alerts,
    mark_triggered,
    get_active_coins,
    get_active_alerts_for_coins,
)
from src.schemas.alert import (
    PriceAlertSchema,
    AlertCreateSchema,
    ActiveCoinsResponse,
    PriceAlertAPIResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/alerts", tags=["Price Alerts"])


@router.get("/active", response_model=PriceAlertAPIResponse)
async def get_all_active_alerts_endpoint(
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(require_auth),
) -> Any:
    """
    Retorna TODAS las alertas con status=ACTIVE de todos los usuarios.
    Usado por el checker de taso-bot en cada ciclo de verificación.
    """
    from sqlalchemy import select as sa_select
    from src.models.price_alert import PriceAlert as PA

    stmt = sa_select(PA).where(PA.status == "ACTIVE")
    result = await db.execute(stmt)
    alertas = list(result.scalars().all())
    return PriceAlertAPIResponse(
        ok=True,
        data=[PriceAlertSchema.model_validate(a) for a in alertas],
        count=len(alertas),
    )


@router.get("/active/coins", response_model=PriceAlertAPIResponse)
async def get_active_coins_endpoint(
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(require_auth),
) -> Any:
    """
    Lista de coins que tienen al menos una alerta ACTIVE.
    Usado por el checker de taso-bot para saber qué precios consultar.
    """
    coins = await get_active_coins(db)
    return PriceAlertAPIResponse(
        ok=True,
        data=ActiveCoinsResponse(coins=coins, count=len(coins)),
        count=len(coins),
    )


@router.get("/{user_id}", response_model=PriceAlertAPIResponse)
async def get_user_alerts_endpoint(
    user_id: int,
    status: str = "ACTIVE",
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(require_auth),
) -> Any:
    """
    Obtiene las alertas de un usuario.

    Query params:
        status: "ACTIVE" | "TRIGGERED" | "ALL" (default: "ACTIVE")
    """
    if status not in ("ACTIVE", "TRIGGERED", "ALL"):
        raise HTTPException(status_code=400, detail="status debe ser ACTIVE, TRIGGERED o ALL")

    alerts = await get_user_alerts(db, user_id=user_id, status=status)
    return PriceAlertAPIResponse(
        ok=True,
        data=[PriceAlertSchema.model_validate(a) for a in alerts],
        count=len(alerts),
    )


@router.post("", response_model=PriceAlertAPIResponse)
async def create_alert_endpoint(
    body: AlertCreateSchema,
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(require_auth),
) -> Any:
    """
    Crea dos alertas de precio (ABOVE + BELOW) para el par user/coin/price.

    Body:
        user_id: Telegram user_id
        coin: Símbolo (ej: "BTC")
        target_price: Precio objetivo (debe ser > 0)
    """
    created = []
    for condition in ("ABOVE", "BELOW"):
        alert = await create_alert(
            db,
            user_id=body.user_id,
            coin=body.coin,
            target_price=body.target_price,
            condition=condition,
            price_at_creation=body.price_at_creation,
        )
        if alert:
            created.append(PriceAlertSchema.model_validate(alert))

    if not created:
        return PriceAlertAPIResponse(
            ok=False,
            error={"code": 500, "message": "Error al guardar alertas en la base de datos"},
        )

    return PriceAlertAPIResponse(
        ok=True,
        data=created,
        count=len(created),
    )


@router.delete("/user/{user_id}", response_model=PriceAlertAPIResponse)
async def delete_all_user_alerts_endpoint(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(require_auth),
) -> Any:
    """Elimina todas las alertas de un usuario."""
    count = await delete_all_user_alerts(db, user_id=user_id)
    return PriceAlertAPIResponse(
        ok=True,
        data={"deleted": count},
        count=count,
    )


@router.delete("/{alert_id}", response_model=PriceAlertAPIResponse)
async def delete_alert_endpoint(
    alert_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(require_auth),
) -> Any:
    """
    Elimina una alerta específica.

    Query params:
        user_id: Telegram user_id (seguridad: solo puede borrar las propias)
    """
    deleted = await delete_alert(db, alert_id=alert_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alerta no encontrada o no pertenece al usuario")
    return PriceAlertAPIResponse(
        ok=True,
        data={"deleted": True, "alert_id": alert_id},
        count=1,
    )


@router.patch("/{alert_id}/trigger", response_model=PriceAlertAPIResponse)
async def trigger_alert_endpoint(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(require_auth),
) -> Any:
    """
    Marca una alerta como TRIGGERED.
    Llamado por el checker de taso-bot tras enviar la notificación al usuario.
    """
    alert = await mark_triggered(db, alert_id=alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    return PriceAlertAPIResponse(
        ok=True,
        data=PriceAlertSchema.model_validate(alert),
        count=1,
    )
