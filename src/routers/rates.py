"""Router para endpoints públicos de tasas."""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query

from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.redis_client import RedisClient, get_redis
from src.services import rates_service
from src.schemas.rates import (
    CurrencyRate,
    LatestRatesResponse,
    LatestRatesData,
    SourceRatesResponse,
    HistoryResponse,
    HistorySnapshot,
    HistoryQueryParams,
    CubanomicHistoryResponse,
    CubanomicHistorySnapshot,
)


logger = logging.getLogger(__name__)


router = APIRouter()


@router.get("/latest", response_model=LatestRatesResponse)
async def get_latest_rates(
    db: AsyncSession = Depends(get_db),
    max_age_minutes: int = Query(
        default=120,
        ge=5,
        le=1440,
        description="Máxima edad de datos en minutos (fallback a histórico si es más viejo)"
    )
) -> LatestRatesResponse:
    """
    Obtiene las últimas tasas de todas las fuentes combinadas.
    
    ESTRATEGIA RESILIENTE:
    - Intenta obtener datos frescos de la DB
    - Si no hay, usa últimos datos históricos disponibles (fallback)
    - El bot SIEMPRE recibe datos válidos (nunca None)
    
    Incluye indicadores de cambio (up/down/neutral) comparados con el snapshot anterior.
    """
    rates_data = await rates_service.get_latest_rates(db, max_age_minutes=max_age_minutes)

    # Encontrar el updated_at más reciente entre todas las fuentes
    updated_at = datetime.now(timezone.utc)

    # Formatear datos para los schemas
    eltoque_rates = {}
    cadeca_rates = {}
    bcc_rates = {}
    binance_rates = {}

    for source, rates in rates_data.items():
        formatted_rates = {}
        for currency, rate_info in rates.items():
            if source == 'cadeca':
                # CADECA tiene buy/sell, usar sell_rate como principal
                formatted_rates[currency] = CurrencyRate(
                    rate=rate_info.get('sell', 0) or 0,
                    buy=rate_info.get('buy'),  # Agregar buy explícitamente
                    sell=rate_info.get('sell'),  # Agregar sell explícitamente
                    change=rate_info.get('change', 'neutral'),
                    prev_rate=rate_info.get('prev_rate')
                )
            else:
                # Otras fuentes usan rate único
                formatted_rates[currency] = CurrencyRate(
                    rate=rate_info.get('rate', 0) or 0,
                    change=rate_info.get('change', 'neutral'),
                    prev_rate=rate_info.get('prev_rate')
                )

        if source == 'eltoque':
            eltoque_rates = formatted_rates
        elif source == 'cadeca':
            cadeca_rates = formatted_rates
        elif source == 'bcc':
            bcc_rates = formatted_rates
        elif source == 'binance':
            binance_rates = formatted_rates

    return LatestRatesResponse(
        ok=True,
        data=LatestRatesData(
            eltoque=eltoque_rates,
            cadeca=cadeca_rates,
            bcc=bcc_rates,
            binance=binance_rates
        ),
        updated_at=updated_at
    )


@router.get("/eltoque", response_model=SourceRatesResponse)
async def get_eltoque_rates(
    db: AsyncSession = Depends(get_db),
    max_age_minutes: int = Query(
        default=120,
        ge=5,
        le=1440,
        description="Máxima edad de datos en minutos (fallback a histórico)"
    )
) -> SourceRatesResponse:
    """
    Obtiene las últimas tasas de ElToque (mercado informal).
    
    ESTRATEGIA RESILIENTE:
    - Si no hay datos frescos, usa últimos datos históricos
    - El bot SIEMPRE recibe datos válidos (nunca None)

    Incluye indicadores de cambio (up/down/neutral) comparados con el snapshot anterior.
    """
    rates, updated_at = await rates_service.get_source_rates(db, 'eltoque', max_age_minutes)

    formatted_rates = {}
    for currency, rate_info in rates.items():
        formatted_rates[currency] = CurrencyRate(
            rate=rate_info.get('rate', 0) or 0,
            change=rate_info.get('change', 'neutral'),
            prev_rate=rate_info.get('prev_rate')
        )

    return SourceRatesResponse(
        source='eltoque',
        rates=formatted_rates,
        updated_at=updated_at or datetime.now(timezone.utc)
    )


@router.get("/cadeca", response_model=SourceRatesResponse)
async def get_cadeca_rates(
    db: AsyncSession = Depends(get_db),
    max_age_minutes: int = Query(
        default=120,
        ge=5,
        le=1440,
        description="Máxima edad de datos en minutos (fallback a histórico)"
    )
) -> SourceRatesResponse:
    """
    Obtiene las últimas tasas de CADECA (oficial, compra/venta).
    
    ESTRATEGIA RESILIENTE:
    - Si no hay datos frescos, usa últimos datos históricos
    - El bot SIEMPRE recibe datos válidos (nunca None)

    Incluye indicadores de cambio (up/down/neutral) comparados con el snapshot anterior.
    """
    rates, updated_at = await rates_service.get_source_rates(db, 'cadeca', max_age_minutes)

    formatted_rates = {}
    for currency, rate_info in rates.items():
        # Para CADECA, incluir buy y sell explícitamente
        formatted_rates[currency] = CurrencyRate(
            rate=rate_info.get('sell', 0) or 0,  # rate principal es sell
            buy=rate_info.get('buy'),  # Agregar buy explícitamente
            sell=rate_info.get('sell'),  # Agregar sell explícitamente
            change=rate_info.get('change', 'neutral'),
            prev_rate=rate_info.get('prev_rate')
        )

    return SourceRatesResponse(
        source='cadeca',
        rates=formatted_rates,
        updated_at=updated_at or datetime.now(timezone.utc)
    )


@router.get("/bcc", response_model=SourceRatesResponse)
async def get_bcc_rates(
    db: AsyncSession = Depends(get_db),
    max_age_minutes: int = Query(
        default=120,
        ge=5,
        le=1440,
        description="Máxima edad de datos en minutos (fallback a histórico)"
    )
) -> SourceRatesResponse:
    """
    Obtiene las últimas tasas de BCC (Banco Central de Cuba, oficial).
    
    ESTRATEGIA RESILIENTE:
    - Si no hay datos frescos, usa últimos datos históricos
    - El bot SIEMPRE recibe datos válidos (nunca None)

    Incluye indicadores de cambio (up/down/neutral) comparados con el snapshot anterior.
    """
    rates, updated_at = await rates_service.get_source_rates(db, 'bcc', max_age_minutes)

    formatted_rates = {}
    for currency, rate_info in rates.items():
        formatted_rates[currency] = CurrencyRate(
            rate=rate_info.get('rate', 0) or 0,
            change=rate_info.get('change', 'neutral'),
            prev_rate=rate_info.get('prev_rate')
        )

    return SourceRatesResponse(
        source='bcc',
        rates=formatted_rates,
        updated_at=updated_at or datetime.now(timezone.utc)
    )


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    source: str = Query(
        default="eltoque",
        description="Fuente de datos (eltoque, cadeca, bcc, binance)"
    ),
    currency: str = Query(
        default="USD",
        description="Moneda a consultar"
    ),
    days: int = Query(
        default=7,
        ge=1,
        le=365,
        description="Días de histórico (1-365)"
    ),
    db: AsyncSession = Depends(get_db)
) -> HistoryResponse:
    """
    Obtiene histórico de tasas para una fuente y moneda específicas.

    - **source**: Fuente de datos (eltoque, cadeca, bcc, binance)
    - **currency**: Moneda a consultar (USD, EUR, etc.)
    - **days**: Días de histórico (1-365, default: 7)
    """
    snapshots = await rates_service.get_history(db, source, currency, days)

    formatted_data = [
        HistorySnapshot(
            source=snap.source,
            currency=snap.currency,
            buy_rate=float(snap.buy_rate) if snap.buy_rate else None,
            sell_rate=float(snap.sell_rate) if snap.sell_rate else None,
            fetched_at=snap.fetched_at
        )
        for snap in snapshots
    ]

    return HistoryResponse(
        ok=True,
        data=formatted_data,
        count=len(formatted_data)
    )


@router.get("/cubanomic", response_model=SourceRatesResponse)
async def get_cubanomic_rates(
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    max_age_minutes: int = Query(
        default=1440,  # 24 hours
        ge=60,
        le=2880,
        description="Máxima edad de datos en minutos"
    )
) -> SourceRatesResponse:
    """
    Obtiene las tasas de Cubanomic (USD/EUR/MLC).

    Datos cacheados en Redis con TTL de 24 horas.

    - **max_age_minutes**: Máxima edad de datos en minutos (default: 1440 = 24h)
    """
    from src.services.rates_service import get_cubanomic_cached

    result = await get_cubanomic_cached(db, redis)

    if not result.get("ok"):
        return SourceRatesResponse(
            source="cubanomic",
            rates={},
            updated_at=datetime.now(timezone.utc)
        )

    # Format rates from result
    latest_data = result.get("data", {})

    # Convert to CurrencyRate format
    formatted_rates = {}
    for currency, rate_info in latest_data.items():
        rate_value = rate_info.get("rate") if isinstance(rate_info, dict) else rate_info
        if rate_value:
            formatted_rates[currency] = CurrencyRate(
                rate=float(rate_value),
                change="neutral",  # Cubanomic doesn't track change yet
                prev_rate=None
            )

    return SourceRatesResponse(
        source="cubanomic",
        rates=formatted_rates,
        updated_at=datetime.now(timezone.utc)
    )


@router.get("/history/cubanomic", response_model=CubanomicHistoryResponse)
async def get_cubanomic_history(
    days: int = Query(
        default=30,
        ge=7,
        le=730,  # 2 years
        description="Días de histórico (7-730)"
    ),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
) -> CubanomicHistoryResponse:
    """
    Obtiene histórico de Cubanomic (USD/EUR/MLC).

    Rangos disponibles: 7d, 14d, 30d, 60d, 90d, 6m (180d), 1y (365d), 2y (730d)
    Datos cacheados en Redis por fuente y rango de días.
    
    El endpoint agrupa los datos por fecha, retornando un punto por día con:
    - usd_rate: tasa del USD
    - eur_rate: tasa del EUR
    - mlc_rate: tasa del MLC
    - fetched_at: fecha de captura
    """
    cache_key = f"cubanomic:history:{days}"

    # Try cache first
    cached = await redis.get(cache_key)
    if cached:
        logger.info(f"♻️ Cubanomic history cache HIT for {days} days")
        # Transform cached data to grouped format
        grouped_data = _group_cubanomic_history_by_date(cached)
        return CubanomicHistoryResponse(
            ok=True,
            data=grouped_data,
            count=len(grouped_data)
        )

    # Fetch from Cubanomic API
    from src.scrapers.cubanomic import fetch_cubanomic
    result = await fetch_cubanomic(days=days)

    if not result.get("ok"):
        return CubanomicHistoryResponse(ok=False, data=[], count=0)

    history = result.get("history", [])

    # Group by date and transform to format expected by frontend
    grouped_data = _group_cubanomic_history_by_date(history)

    # Cache for 1 hour (historical data changes less frequently)
    await redis.set(cache_key, history, ttl=3600)

    return CubanomicHistoryResponse(
        ok=True,
        data=grouped_data,
        count=len(grouped_data)
    )


def _group_cubanomic_history_by_date(history: list) -> list[CubanomicHistorySnapshot]:
    """
    Agrupa histórico de Cubanomic por fecha, combinando USD/EUR/MLC rates.
    
    Args:
        history: Lista de puntos {"date": "...", "currency": "USD", "rate": 517.26}
    
    Returns:
        Lista agrupada por fecha con todos los rates:
        [
            {
                "source": "cubanomic",
                "currency": "MULTI",
                "fetched_at": "2026-03-28T00:00:00Z",
                "usd_rate": 517.26,
                "eur_rate": 582.36,
                "mlc_rate": 394.82
            }
        ]
    """
    from collections import defaultdict
    
    # Group by date
    by_date: dict[str, dict[str, float]] = defaultdict(dict)
    
    for point in history:
        date = point.get("date")
        currency = point.get("currency")
        rate = point.get("rate")
        
        if date and currency and rate is not None:
            by_date[date][currency] = rate
    
    # Build grouped snapshots
    grouped = []
    for date, rates in sorted(by_date.items()):
        usd_rate = rates.get("USD")
        eur_rate = rates.get("EUR")
        mlc_rate = rates.get("MLC")
        
        snapshot = CubanomicHistorySnapshot(
            source="cubanomic",
            currency="MULTI",
            buy_rate=usd_rate,  # USD as primary
            sell_rate=eur_rate,  # EUR as secondary
            fetched_at=date,
            usd_rate=usd_rate,
            eur_rate=eur_rate,
            mlc_rate=mlc_rate
        )
        grouped.append(snapshot)
    
    return grouped
