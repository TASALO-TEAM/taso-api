"""Router para el sistema de anuncios (ads).

Endpoints públicos (sin auth): pensados para taso-bot y, a futuro, taso-app
y taso-ext, sin necesidad de compartir la admin key con un frontend público.

Endpoints admin (X-API-Key): gestión completa, usados por /ads en taso-bot.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.middleware.auth import require_auth
from src.services import ad_service
from src.schemas.ad import (
    AdSchema,
    AdPublicSchema,
    AdCreateSchema,
    AdUpdateSchema,
    AdAPIResponse,
)

logger = logging.getLogger(__name__)

# Router público: sin dependencies de auth (mismo criterio que routers/rates.py)
router = APIRouter()

# Router admin: requiere X-API-Key en todos sus endpoints (mismo criterio que routers/admin.py)
admin_router = APIRouter(dependencies=[Depends(require_auth)])


# ── Endpoints públicos (sin auth) ───────────────────────────────────────────


@router.get("/active", response_model=AdAPIResponse)
async def get_active_ads_endpoint(db: AsyncSession = Depends(get_db)) -> Any:
    """Lista los anuncios activos (schema público, sin campos sensibles).

    Usado por taso-bot y, a futuro, por taso-app / taso-ext.
    """
    ads = await ad_service.list_ads(db, active_only=True)
    return AdAPIResponse(
        ok=True,
        data=[AdPublicSchema.model_validate(a) for a in ads],
        count=len(ads),
    )


@router.get("/random", response_model=AdAPIResponse)
async def get_random_ad_endpoint(db: AsyncSession = Depends(get_db)) -> Any:
    """Devuelve un anuncio activo elegido al azar (ponderado por weight).

    data=null si no hay ningún anuncio activo (no es un error).
    """
    ad = await ad_service.get_random_active_ad(db)
    return AdAPIResponse(
        ok=True,
        data=AdPublicSchema.model_validate(ad) if ad else None,
        count=1 if ad else 0,
    )


# ── Endpoints admin (X-API-Key) ──────────────────────────────────────────────


@admin_router.get("", response_model=AdAPIResponse)
async def list_ads_endpoint(db: AsyncSession = Depends(get_db)) -> Any:
    """Lista TODOS los anuncios (activos e inactivos). Uso: gestión desde /ads."""
    ads = await ad_service.list_ads(db, active_only=False)
    return AdAPIResponse(
        ok=True,
        data=[AdSchema.model_validate(a) for a in ads],
        count=len(ads),
    )


@admin_router.post("", response_model=AdAPIResponse)
async def create_ad_endpoint(
    body: AdCreateSchema,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Crea un anuncio nuevo."""
    ad = await ad_service.create_ad(
        db,
        text=body.text,
        is_sponsored=body.is_sponsored,
        weight=body.weight,
        created_by=body.created_by,
    )
    if not ad:
        return AdAPIResponse(
            ok=False,
            error={"code": 500, "message": "Error al guardar el anuncio en la base de datos"},
        )
    return AdAPIResponse(ok=True, data=AdSchema.model_validate(ad), count=1)


@admin_router.patch("/{ad_id}", response_model=AdAPIResponse)
async def update_ad_endpoint(
    ad_id: int,
    body: AdUpdateSchema,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Edita un anuncio: texto, activo/inactivo, patrocinado/aviso o peso."""
    ad = await ad_service.update_ad(
        db,
        ad_id=ad_id,
        text=body.text,
        is_active=body.is_active,
        is_sponsored=body.is_sponsored,
        weight=body.weight,
    )
    if not ad:
        raise HTTPException(status_code=404, detail="Anuncio no encontrado")
    return AdAPIResponse(ok=True, data=AdSchema.model_validate(ad), count=1)


@admin_router.delete("/{ad_id}", response_model=AdAPIResponse)
async def delete_ad_endpoint(
    ad_id: int,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Elimina un anuncio definitivamente."""
    deleted = await ad_service.delete_ad(db, ad_id=ad_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Anuncio no encontrado")
    return AdAPIResponse(ok=True, data={"deleted": True, "ad_id": ad_id}, count=1)
