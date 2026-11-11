"""Router para endpoints públicos de tasas."""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, Query, Request, Response

from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.redis_client import RedisClient
from src.services import fuel_service, history_service, rates_service
from src.scrapers.qvapay import qvapay_meta
from src.schemas.rates import (
    QvaPayRate,
    QvaPayRatesResponse,
    CurrencyRate,
    LatestRatesResponse,
    LatestRatesData,
    SourceRatesResponse,
    HistoryResponse,
    HistorySnapshot,
    HistoryQueryParams,
)
from src.schemas.history import (
    DailyHistoryResponse,
    DailyPoint,
    LocalHistoryResponse,
    LocalHistorySnapshot,
    SummaryHistoryResponse,
)
from src.models.rates import HistorySnapshot as HistorySnapshotModel


logger = logging.getLogger(__name__)


# Las tasas solo cambian cuando el scheduler guarda un ciclo nuevo (cada 15 min): los clientes
# pueden reutilizar la respuesta unos segundos y revalidar con ETag sin recibir el cuerpo.
CACHE_CONTROL = "public, max-age=30"


def _conditional(
    request: Request, response: Response, key: str, stamps: dict[str, datetime]
) -> Response | None:
    """Pone ETag + Cache-Control; devuelve un 304 si el cliente ya tiene esta versión.

    El ETag sale de la hora real del dato (fetched_at por fuente) y de los parámetros, no del
    cuerpo: así no cambia entre peticiones mientras no haya tasas nuevas. Sin datos, no hay ETag.
    """
    if not stamps:
        return None
    raw = key + "|" + ",".join(f"{k}:{v.isoformat()}" for k, v in sorted(stamps.items()))
    etag = 'W/"' + hashlib.blake2s(raw.encode(), digest_size=8).hexdigest() + '"'
    headers = {"ETag": etag, "Cache-Control": CACHE_CONTROL}
    sent = [v.strip() for v in request.headers.get("if-none-match", "").split(",")]
    if etag in sent:
        return Response(status_code=304, headers=headers)
    response.headers.update(headers)
    return None


router = APIRouter()


def _latest_fetched_at(rates: dict) -> datetime | None:
    """Hora real del dato de una fuente: el `fetched_at` más reciente entre sus monedas.

    get_latest_rates() ya incluye `fetched_at` (ISO) en cada moneda. Devuelve None si ninguna
    lo trae o no se puede interpretar. Un valor sin zona horaria se toma como UTC.
    """
    stamps: list[datetime] = []
    for info in rates.values():
        raw = info.get("fetched_at") if isinstance(info, dict) else None
        if not isinstance(raw, str):
            continue
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            continue
        stamps.append(parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc))
    return max(stamps) if stamps else None


@router.get("/latest", response_model=LatestRatesResponse)
async def get_latest_rates(
    request: Request,
    response: Response,
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
    rates_data = await rates_service.get_latest_rates(
        db, max_age_minutes=max_age_minutes, use_cache=True
    )

    # Encontrar el updated_at más reciente entre todas las fuentes
    updated_at = datetime.now(timezone.utc)

    # Formatear datos para los schemas
    eltoque_rates = {}
    bcc_rates = {}
    binance_rates = {}
    qvapay_rates = {}

    sources_updated_at: dict[str, datetime] = {}

    for source, rates in rates_data.items():
        fetched_at = _latest_fetched_at(rates)
        if fetched_at is not None:
            sources_updated_at[source] = fetched_at
        formatted_rates = {}
        for currency, rate_info in rates.items():
            if source == 'qvapay':
                # QvaPay: rate = promedio (compra + venta) / 2, ya calculado por el servicio.
                # Expone buy/sell explícitos y name/kind/count.
                formatted_rates[currency] = QvaPayRate(
                    rate=rate_info.get('rate', 0) or 0,
                    buy=rate_info.get('buy'),
                    sell=rate_info.get('sell'),
                    change=rate_info.get('change', 'neutral'),
                    prev_rate=rate_info.get('prev_rate'),
                    **qvapay_meta(currency),
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
        elif source == 'bcc':
            bcc_rates = formatted_rates
        elif source == 'binance':
            binance_rates = formatted_rates
        elif source == 'qvapay':
            qvapay_rates = formatted_rates

    not_modified = _conditional(request, response, f"latest|{max_age_minutes}", sources_updated_at)
    if not_modified is not None:
        return not_modified

    return LatestRatesResponse(
        ok=True,
        data=LatestRatesData(
            eltoque=eltoque_rates,
            bcc=bcc_rates,
            binance=binance_rates,
            qvapay=qvapay_rates,
        ),
        updated_at=updated_at,
        sources_updated_at=sources_updated_at,
    )


@router.get("/eltoque", response_model=SourceRatesResponse)
async def get_eltoque_rates(
    request: Request,
    response: Response,
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
    rates, updated_at = await rates_service.get_source_rates(
        db, 'eltoque', max_age_minutes, use_cache=True
    )
    not_modified = _conditional(
        request, response, f"eltoque|{max_age_minutes}", {"eltoque": updated_at} if updated_at else {}
    )
    if not_modified is not None:
        return not_modified

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


@router.get("/qvapay", response_model=QvaPayRatesResponse)
async def get_qvapay_rates(
    db: AsyncSession = Depends(get_db),
    max_age_minutes: int = Query(
        default=120,
        ge=5,
        le=1440,
        description="Máxima edad de datos en minutos (fallback a histórico)"
    )
) -> QvaPayRatesResponse:
    """
    Obtiene las últimas tasas P2P de QvaPay por método de pago.

    Cada valor es "cuánto de ese método por 1 USD de QvaPay" (CUP, MLC, TROPIPAY, ETECSA,
    ZELLE, CLASICA, BOLSATM, BANDECPREPAGO, SBERBANK, CUPCASH); no todos son CUP por unidad.
    ``rate`` es el promedio (compra + venta) / 2; ``buy`` y ``sell`` son los promedios de
    compra y venta. Los métodos sin operaciones recientes no aparecen.

    Incluye indicadores de cambio (up/down/neutral) calculados sobre el promedio.
    """
    rates, updated_at = await rates_service.get_source_rates(db, 'qvapay', max_age_minutes)

    formatted_rates = {}
    for currency, rate_info in rates.items():
        formatted_rates[currency] = QvaPayRate(
            rate=rate_info.get('rate', 0) or 0,
            buy=rate_info.get('buy'),
            sell=rate_info.get('sell'),
            change=rate_info.get('change', 'neutral'),
            prev_rate=rate_info.get('prev_rate'),
            **qvapay_meta(currency),
        )

    return QvaPayRatesResponse(
        source='qvapay',
        rates=formatted_rates,
        updated_at=updated_at or datetime.now(timezone.utc)
    )


@router.get("/fuel", response_model=SourceRatesResponse)
async def get_fuel_rates(
    db: AsyncSession = Depends(get_db),
    max_age_minutes: int = Query(
        default=60,
        ge=1,
        le=1440,
        description="Máxima edad de datos en minutos (fallback a histórico)"
    ),
) -> SourceRatesResponse:
    """
    Obtiene los precios de combustible del mercado informal (ElToque).

    Este endpoint es independiente del ciclo de ``rates_service``.
    Hace scraping bajo demanda y persiste los resultados en la tabla
    ``rate_snapshots`` con ``source='fuel'``.
    """
    rates, updated_at = await fuel_service.get_fuel_rates(db, max_age_minutes)

    formatted_rates = {}
    for currency, rate_info in rates.items():
        formatted_rates[currency] = CurrencyRate(
            rate=rate_info.get("rate", 0) or 0,
            buy=rate_info.get("buy"),
            sell=rate_info.get("sell"),
            change=rate_info.get("change", "neutral"),
            prev_rate=rate_info.get("prev_rate"),
        )

    return SourceRatesResponse(
        source="fuel",
        rates=formatted_rates,
        updated_at=updated_at or datetime.now(timezone.utc),
    )


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    source: str = Query(
        default="eltoque",
        description="Fuente de datos (eltoque, bcc, binance, qvapay)"
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

    - **source**: Fuente de datos (eltoque, bcc, binance, qvapay)
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


@router.get("/history/daily", response_model=DailyHistoryResponse)
async def get_daily_history(
    source: Literal["eltoque", "bcc", "binance", "qvapay"] = Query(
        default="eltoque", description="Fuente de datos"
    ),
    currency: str = Query(default="USD", description="Moneda a consultar"),
    days: int = Query(default=180, ge=1, le=365, description="Días de Cuba hacia atrás (1-365)"),
    db: AsyncSession = Depends(get_db),
) -> DailyHistoryResponse:
    """
    Serie diaria liviana de una fuente y moneda (para el detalle histórico de la app).

    Un punto por **fecha de Cuba** (America/Havana): la lectura más cercana a las 7:00 a. m. de ese día.
    Los días sin lectura no aparecen. En QvaPay, ``rate`` es el promedio de compra y venta.
    """
    code = currency.strip().upper()
    points = await history_service.get_daily(db, source, code, days)
    return DailyHistoryResponse(
        source=source,
        currency=code,
        days=days,
        data=[DailyPoint(date=day, rate=rate) for day, rate in points],
    )


@router.get("/history/summary", response_model=SummaryHistoryResponse)
async def get_history_summary(
    days: int = Query(default=30, ge=1, le=90, description="Días de Cuba hacia atrás (1-90)"),
    db: AsyncSession = Depends(get_db),
) -> SummaryHistoryResponse:
    """
    Resumen diario de todas las fuentes y monedas en una sola respuesta (fondo de las tarjetas de la app).

    Misma regla que ``/history/daily``. Respuesta cacheada unos minutos en memoria.
    """
    data = await history_service.get_summary(db, days)
    return SummaryHistoryResponse(
        days=days,
        data={
            source: {
                currency: [DailyPoint(date=day, rate=rate) for day, rate in points]
                for currency, points in currencies.items()
            }
            for source, currencies in data.items()
        },
    )


@router.get("/history/local", response_model=LocalHistoryResponse)
async def get_local_history(
    days: int = Query(
        default=1,
        ge=1,
        le=730,
        description="Número de días de histórico (1-730). Default: 1."
    ),
    db: AsyncSession = Depends(get_db)
) -> LocalHistoryResponse:
    """
    Obtiene histórico local de tasas (USD/EUR/MLC) desde la base de datos.

    Los datos se recolectan automáticamente cada 15 minutos del refresh cycle.

    Args:
        days: Número de días de histórico (1-730). Default: 1.

    Returns:
        Lista de snapshots con tasas USD/EUR/MLC agrupadas por fecha.
    """
    from sqlalchemy import select
    from datetime import timedelta

    # Calculate date range
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)

    # Query history snapshots
    result = await db.execute(
        select(HistorySnapshotModel)
        .where(HistorySnapshotModel.fetched_at >= start_date)
        .where(HistorySnapshotModel.fetched_at <= end_date)
        .order_by(HistorySnapshotModel.fetched_at.asc())
    )

    snapshots = result.scalars().all()

    # Convert to response format (group by date, average per day)
    grouped_data = _group_local_history_by_date(snapshots)

    return LocalHistoryResponse(
        ok=True,
        data=grouped_data,
        count=len(grouped_data)
    )


def _group_local_history_by_date(snapshots: list) -> list[LocalHistorySnapshot]:
    """
    Agrupa snapshots locales por fecha, promediando USD/EUR/MLC rates del día.

    Args:
        snapshots: List of HistorySnapshot from database query

    Returns:
        List of LocalHistorySnapshot grouped by date
    """
    from collections import defaultdict

    # Group by date
    by_date: dict = defaultdict(lambda: {
        'usd': [], 'eur': [], 'mlc': []
    })

    for snapshot in snapshots:
        snapshot_date = snapshot.fetched_at.date()

        # Collect all available rates for this date
        if snapshot.eltoque_usd is not None:
            by_date[snapshot_date]['usd'].append(snapshot.eltoque_usd)
        if snapshot.bcc_usd is not None:
            by_date[snapshot_date]['usd'].append(snapshot.bcc_usd)

        if snapshot.eltoque_eur is not None:
            by_date[snapshot_date]['eur'].append(snapshot.eltoque_eur)
        if snapshot.bcc_eur is not None:
            by_date[snapshot_date]['eur'].append(snapshot.bcc_eur)

        if snapshot.eltoque_mlc is not None:
            by_date[snapshot_date]['mlc'].append(snapshot.eltoque_mlc)
        if snapshot.bcc_mlc is not None:
            by_date[snapshot_date]['mlc'].append(snapshot.bcc_mlc)

    # Calculate daily averages
    result = []
    for snapshot_date in sorted(by_date.keys()):
        data = by_date[snapshot_date]

        usd_avg = sum(data['usd']) / len(data['usd']) if data['usd'] else None
        eur_avg = sum(data['eur']) / len(data['eur']) if data['eur'] else None
        mlc_avg = sum(data['mlc']) / len(data['mlc']) if data['mlc'] else None

        # Use midnight UTC for the date
        fetched_at = datetime.combine(snapshot_date, datetime.min.time(), tzinfo=timezone.utc)

        result.append(LocalHistorySnapshot(
            fetched_at=fetched_at,
            usd_rate=usd_avg,
            eur_rate=eur_avg,
            mlc_rate=mlc_avg
        ))

    return result
