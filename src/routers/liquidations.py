"""Router de GET /liquidaciones (taso-bot M3a). Solo lectura, requiere clave."""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.middleware.auth import require_auth
from src.schemas.liquidations import LiqItem, LiqMeta, LiqResponse
from src.services import liquidations as svc

router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("", response_model=LiqResponse)
async def get_liquidations(
    window: Literal["5m", "15m", "1h", "4h", "24h"] = Query("1h", description="Ventana de tiempo"),
    by: Literal["symbol", "exchange"] = Query("symbol", description="Agrupar por moneda o por exchange"),
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_auth),
) -> LiqResponse:
    """Liquidaciones de futuros (Binance+Bybit+OKX), long/short en USD, el mayor primero."""
    res = await svc.get_liquidations(db, window, by)
    return LiqResponse(
        data=[
            LiqItem(key=r.key, long_usd=r.long_usd, short_usd=r.short_usd, total_usd=r.total_usd)
            for r in res.data
        ],
        meta=LiqMeta(window=window, by=by, since=res.since, coverage_from=res.coverage_from),
    )
