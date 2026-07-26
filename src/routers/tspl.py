"""Router for /tspl/subscriptions/* endpoints.

Suscripción de usuarios a hasta 2 horarios diarios de envío de /tspl.
Ver docs/plans/2026-07-24-tspl-suscripcion-horarios.md
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.middleware.auth import require_auth
from src.services import tspl_service
from src.schemas.tspl import (
    TsplSubscriptionCreate,
    TsplSubscriptionResponse,
    TsplSubscriptionListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Tspl"])


# ── User-owned subscription endpoints (no admin key required) ──────────────


@router.get("/subscriptions/me/{user_id}", response_model=TsplSubscriptionListResponse)
async def get_my_subscriptions(user_id: int, db: AsyncSession = Depends(get_db)):
    """Lista los horarios (0, 1 o 2) a los que está suscrito el usuario."""
    rows = await tspl_service.get_my_subscriptions(db, user_id)
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


@router.post("/subscriptions/me/{user_id}", response_model=TsplSubscriptionResponse)
async def add_my_subscription(user_id: int, body: TsplSubscriptionCreate, db: AsyncSession = Depends(get_db)):
    """Agrega un horario a la suscripción del usuario (máximo 2 activos)."""
    if body.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot subscribe on behalf of another user",
        )
    try:
        sub = await tspl_service.add_my_subscription(db, user_id, body.hour)
    except ValueError as e:
        if str(e) == "max_subscriptions_reached":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Máximo {tspl_service.MAX_SUBSCRIPTIONS_PER_USER} horarios por usuario — elimina uno antes de agregar otro",
            )
        raise
    return TsplSubscriptionResponse(
        id=sub.id, user_id=sub.user_id, hour=sub.hour, created_at=sub.created_at,
    )


@router.delete("/subscriptions/me/{user_id}/{hour}")
async def delete_my_subscription(user_id: int, hour: int, db: AsyncSession = Depends(get_db)):
    """Elimina un horario puntual de la suscripción del usuario."""
    ok = await tspl_service.delete_my_subscription(db, user_id, hour)
    return {"ok": ok, "deleted": ok, "user_id": user_id, "hour": hour}


@router.delete("/subscriptions/me/{user_id}")
async def delete_all_my_subscriptions(user_id: int, db: AsyncSession = Depends(get_db)):
    """Elimina TODOS los horarios de la suscripción del usuario."""
    count = await tspl_service.delete_all_my_subscriptions(db, user_id)
    return {"ok": True, "deleted_count": count, "user_id": user_id}


# ── Admin (para el dispatcher del bot) ──────────────────────────────────


@router.get("/subscriptions", response_model=TsplSubscriptionListResponse)
async def list_all_subscriptions(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    """Lista TODAS las suscripciones de todos los usuarios — usado por el
    dispatcher horario de taso-bot (tspl_alert_dispatcher.py)."""
    return await tspl_service.get_all_subscriptions(db)
