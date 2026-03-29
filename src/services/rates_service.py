"""Rates business logic service."""

import asyncio
import json
import logging
from typing import Any, Literal
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.scrapers.eltoque import fetch_eltoque
from src.scrapers.binance import fetch_binance
from src.scrapers.cadeca import fetch_cadeca
from src.scrapers.bcc import fetch_bcc
from src.scrapers.cubanomic import fetch_cubanomic
from src.models.rate_snapshot import RateSnapshot
from src.models.rates import CubanomicRate

logger = logging.getLogger(__name__)


# Legacy: tolerancia de legacy/tasa.py (TOLERANCIA = 0.0001)
CHANGE_TOLERANCE = 0.0001
CURRENCY_MAP = {"USDT_TRC20": "USDT", "ECU": "EUR"}

ChangeDirection = Literal["up", "down", "neutral"]


def calculate_change(current: float, previous: float | None) -> ChangeDirection:
    """
    Calcula dirección del cambio entre tasa actual y anterior.

    Legacy pattern: lógica de comparación de legacy/tasa.py

    Args:
        current: Tasa actual
        previous: Tasa anterior (None si no hay historial)

    Returns:
        'up' si subió, 'down' si bajó, 'neutral' si no cambió significativamente
    """
    if previous is None:
        return "neutral"

    difference = current - previous

    if difference > CHANGE_TOLERANCE:
        return "up"
    elif difference < -CHANGE_TOLERANCE:
        return "down"
    else:
        return "neutral"


async def _fetch_safe(coro_func, timeout_secs: int, source_name: str) -> Any:
    """
    Ejecuta un scraper asíncrono con timeout individual.
    Si falla, retorna None sin afectar los demás scrapers.

    Legacy pattern: fetch_safe() de legacy/tasa.py
    """
    try:
        return await asyncio.wait_for(coro_func(), timeout=timeout_secs)
    except asyncio.TimeoutError:
        print(f"⚠️ Timeout en {source_name} ({timeout_secs}s)")
        return None
    except Exception as e:
        print(f"❌ Error en {source_name}: {e}")
        return None


async def fetch_all_sources() -> dict[str, Any]:
    """
    Ejecuta los 4 scrapers en paralelo con timeouts individuales.

    Timeouts:
    - ElToque: 12s (API externa con auth)
    - Binance: 10s (API pública rápida)
    - CADECA: 8s (web scraper inestable)
    - BCC: 10s (web scraper oficial)

    Returns:
        dict con claves 'eltoque', 'binance', 'cadeca', 'bcc'
        Cada valor es el resultado del scraper o None si falló
    """
    results = await asyncio.gather(
        _fetch_safe(fetch_eltoque, 12, "ElToque"),
        _fetch_safe(fetch_binance, 10, "Binance"),
        _fetch_safe(fetch_cadeca, 8, "CADECA"),
        _fetch_safe(fetch_bcc, 10, "BCC"),
        return_exceptions=False,
    )

    return {
        "eltoque": results[0],
        "binance": results[1],
        "cadeca": results[2],
        "bcc": results[3],
    }


def _normalize_eltoque_data(data: dict) -> list[dict]:
    """
    Normaliza datos de ElToque a lista de {currency, buy_rate, sell_rate}.

    Legacy: estructura de legacy/tasa.py -> tasas_actuales
    """
    tasas = data.get("tasas", {})
    result = []

    for currency, rate in tasas.items():
        # ElToque usa tasa única (venta)
        result.append(
            {
                "currency": CURRENCY_MAP.get(currency, currency),
                "buy_rate": None,  # ElToque no tiene compra
                "sell_rate": float(rate),
            }
        )

    return result


def _normalize_cadeca_bcc_data(data: dict, source: str) -> list[dict]:
    """
    Normaliza datos de CADECA/BCC a lista de {currency, buy_rate, sell_rate}.

    CADECA: {'USD': {'compra': 120, 'venta': 125}}
    BCC: {'USD': 125.0}  # Solo venta
    """
    result = []

    for currency, value in data.items():
        if isinstance(value, dict):
            # CADECA format
            result.append(
                {
                    "currency": currency,
                    "buy_rate": float(value.get("compra", 0)),
                    "sell_rate": float(value.get("venta", 0)),
                }
            )
        else:
            # BCC format (single rate)
            result.append(
                {"currency": currency, "buy_rate": None, "sell_rate": float(value)}
            )

    return result


def _normalize_binance_data(data: dict) -> list[dict]:
    """
    Normaliza datos de Binance a lista de {currency, buy_rate, sell_rate}.

    Binance: {'BTCUSDT': '45000.00', 'ETHUSDT': '2500.00'}
    """
    result = []

    for symbol, price in data.items():
        # Extraer currency del símbolo (BTCUSDT -> BTC)
        currency = symbol.replace("USDT", "")
        result.append(
            {"currency": currency, "buy_rate": None, "sell_rate": float(price)}
        )

    return result


async def save_snapshot(session: AsyncSession, source: str, data: Any) -> None:
    """
    Persiste snapshot de tasas en la base de datos.

    Args:
        session: SQLAlchemy async session
        source: 'eltoque' | 'binance' | 'cadeca' | 'bcc'
        data: Datos crudos del scraper

    Legacy pattern: save_*_history() de legacy/tasa_manager.py
    """
    if data is None:
        print(f"⚠️ No se guardó snapshot de {source}: datos None")
        return

    # Normalizar datos según fuente
    if source == "eltoque":
        normalized = _normalize_eltoque_data(data)
    elif source == "cadeca":
        normalized = _normalize_cadeca_bcc_data(data, source)
    elif source == "bcc":
        normalized = _normalize_cadeca_bcc_data(data, source)
    elif source == "binance":
        normalized = _normalize_binance_data(data)
    else:
        print(f"⚠️ Fuente desconocida: {source}")
        return

    # Crear registros
    now = datetime.now(timezone.utc)
    snapshots = []

    for item in normalized:
        snapshot = RateSnapshot(
            source=source,
            currency=item["currency"],
            buy_rate=item["buy_rate"],
            sell_rate=item["sell_rate"],
            fetched_at=now,
        )
        snapshots.append(snapshot)

    session.add_all(snapshots)
    print(f"✅ Guardados {len(snapshots)} snapshots de {source}")


async def _get_previous_snapshot(
    session: AsyncSession, source: str, currency: str, current_fetched_at: datetime
) -> float | None:
    """
    Obtiene la tasa anterior para una moneda y fuente específicas.

    Args:
        session: SQLAlchemy async session
        source: Fuente de datos
        currency: Moneda
        current_fetched_at: Timestamp del snapshot actual

    Returns:
        Tasa anterior (sell_rate) o None si no hay historial
    """
    stmt = (
        select(RateSnapshot.sell_rate)
        .where(
            RateSnapshot.source == source,
            RateSnapshot.currency == currency,
            RateSnapshot.fetched_at < current_fetched_at,
        )
        .order_by(RateSnapshot.fetched_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.first()
    return float(row[0]) if row and row[0] else None


async def get_latest_rates(
    session: AsyncSession, max_age_minutes: int = 120
) -> dict[str, dict]:
    """
    Obtiene el snapshot más reciente de cada fuente con estrategia resiliente.

    ESTRATEGIA DE FALLBACK EN CASCADA:
    1. Intenta obtener datos del timestamp más reciente de TODAS las fuentes
    2. Si una fuente no tiene datos en ese timestamp, busca sus últimos datos válidos
    3. Si no hay datos históricos, retorna dict vacío (pero nunca None)

    El bot SIEMPRE recibe datos válidos - si son viejos, se marca con data_age_minutes.

    Args:
        session: SQLAlchemy async session
        max_age_minutes: Máxima edad de datos en minutos antes de marcar como stale

    Returns:
        dict con estructura:
        {
            'eltoque': {'USD': {'rate': 365.0, 'change': 'up'}},
            'binance': {'BTC': {'rate': 45000.0}},
            'cadeca': {'USD': {'buy': 120.0, 'sell': 125.0}},
            'bcc': {'USD': {'rate': 125.0}}
        }
    """
    from datetime import timedelta

    result = {}
    now = datetime.now(timezone.utc)

    for source in ["eltoque", "binance", "cadeca", "bcc"]:
        snapshots = []
        age_minutes = None

        # ESTRATEGIA 1: Intentar obtener datos del timestamp más reciente de ESTA fuente
        subquery = (
            select(func.max(RateSnapshot.fetched_at))
            .where(RateSnapshot.source == source)
            .scalar_subquery()
        )

        # Obtener todos los registros con ese fetched_at
        stmt = select(RateSnapshot).where(
            RateSnapshot.source == source, RateSnapshot.fetched_at == subquery
        )

        query_result = await session.execute(stmt)
        snapshots = query_result.scalars().all()

        # ESTRATEGIA 2: Fallback - si no hay datos en este timestamp, buscar últimos disponibles
        if not snapshots:
            print(f"⚠️ {source}: Sin datos en timestamp máximo, buscando histórico...")

            # Buscar últimos 15 snapshots disponibles (cualquier fecha)
            fallback_stmt = (
                select(RateSnapshot)
                .where(RateSnapshot.source == source)
                .order_by(RateSnapshot.fetched_at.desc())
                .limit(15)
            )
            fallback_result = await session.execute(fallback_stmt)
            fallback_snapshots = fallback_result.scalars().all()

            if not fallback_snapshots:
                print(
                    f"❌ {source}: Sin datos históricos en DB - retornando dict vacío"
                )
                result[source] = {}
                continue
            else:
                print(
                    f"✅ {source}: Usando fallback con {len(fallback_snapshots)} registros históricos"
                )

                # ESTRATEGIA 3: Agrupar por currency y tomar el más reciente de cada uno
                # Esto es importante porque podemos tener múltiples snapshots de diferentes fechas
                latest_by_currency: dict[str, RateSnapshot] = {}
                for snap in fallback_snapshots:
                    if snap.currency not in latest_by_currency:
                        latest_by_currency[snap.currency] = snap

                snapshots = list(latest_by_currency.values())
                print(
                    f"✅ {source}: {len(snapshots)} monedas únicas después de agrupar"
                )

        # Calcular edad de los datos
        if snapshots:
            data_age = now - snapshots[0].fetched_at
            age_minutes = int(data_age.total_seconds() / 60)
            if age_minutes > max_age_minutes:
                print(
                    f"⚠️ {source}: Datos con {age_minutes}min de antigüedad (stale > {max_age_minutes}min)"
                )
            else:
                print(f"✅ {source}: Datos frescos ({age_minutes}min)")

        # Formatear según fuente - NUNCA retornar None, siempre dict
        if source in ["eltoque", "binance", "bcc"]:
            formatted = {}
            for snap in snapshots:
                # Validar que sell_rate no sea None
                if snap.sell_rate is None:
                    print(f"⚠️ {source}/{snap.currency}: sell_rate es None, saltando")
                    continue

                rate = float(snap.sell_rate)

                # Obtener tasa anterior para calcular cambio
                prev_rate = await _get_previous_snapshot(
                    session, source, snap.currency, snap.fetched_at
                )

                formatted[snap.currency] = {
                    "rate": rate,
                    "change": calculate_change(rate, prev_rate),
                    "prev_rate": prev_rate,
                    "fetched_at": snap.fetched_at.isoformat(),
                    "data_age_minutes": age_minutes,
                }

            result[source] = formatted
            if not formatted:
                print(f"⚠️ {source}: No se pudo formatear ningún dato válido")

        elif source == "cadeca":
            formatted = {}
            for snap in snapshots:
                # CADECA necesita al menos buy_rate o sell_rate
                if snap.buy_rate is None and snap.sell_rate is None:
                    print(
                        f"⚠️ {source}/{snap.currency}: buy_rate y sell_rate son None, saltando"
                    )
                    continue

                # Obtener tasa anterior para calcular cambio (usar sell_rate)
                prev_rate = None
                if snap.sell_rate:
                    prev_rate = await _get_previous_snapshot(
                        session, source, snap.currency, snap.fetched_at
                    )

                formatted[snap.currency] = {
                    "buy": float(snap.buy_rate) if snap.buy_rate else None,
                    "sell": float(snap.sell_rate) if snap.sell_rate else None,
                    "change": calculate_change(
                        float(snap.sell_rate) if snap.sell_rate else 0, prev_rate
                    ),
                    "prev_rate": prev_rate,
                    "fetched_at": snap.fetched_at.isoformat(),
                    "data_age_minutes": age_minutes,
                }

            result[source] = formatted
            if not formatted:
                print(f"⚠️ {source}: No se pudo formatear ningún dato válido")

    # Debug final
    total_rates = sum(len(rates) for rates in result.values())
    print(f"✅ get_latest_rates: {total_rates} tasas en total de 4 fuentes")

    return result


async def get_source_rates(
    session: AsyncSession, source: str, max_age_minutes: int = 120
) -> tuple[dict[str, dict], datetime | None]:
    """
    Obtiene tasas de una fuente específica con cambio calculado y estrategia resiliente.

    ESTRATEGIA DE FALLBACK:
    1. Intenta obtener datos del timestamp más reciente
    2. Si no hay, busca últimos datos históricos disponibles
    3. Retorna dict vacío (nunca None) si no hay datos

    Args:
        session: SQLAlchemy async session
        source: 'eltoque' | 'cadeca' | 'bcc' | 'binance'
        max_age_minutes: Máxima edad de datos antes de marcar como stale

    Returns:
        Tupla con (dict de tasas, timestamp actualizado)
        - dict vacío si no hay datos disponibles
    """
    from datetime import timedelta

    now = datetime.now(timezone.utc)

    # ESTRATEGIA 1: Intentar obtener datos del timestamp más reciente
    subquery = (
        select(func.max(RateSnapshot.fetched_at))
        .where(RateSnapshot.source == source)
        .scalar_subquery()
    )

    stmt = select(RateSnapshot).where(
        RateSnapshot.source == source, RateSnapshot.fetched_at == subquery
    )

    query_result = await session.execute(stmt)
    snapshots = query_result.scalars().all()

    # ESTRATEGIA 2: Fallback - buscar histórico si no hay datos recientes
    if not snapshots:
        print(f"⚠️ {source}: Sin datos recientes, buscando histórico...")

        fallback_stmt = (
            select(RateSnapshot)
            .where(RateSnapshot.source == source)
            .order_by(RateSnapshot.fetched_at.desc())
            .limit(15)
        )
        fallback_result = await session.execute(fallback_stmt)
        fallback_snapshots = fallback_result.scalars().all()

        if not fallback_snapshots:
            print(f"❌ {source}: Sin datos históricos - retornando dict vacío")
            return {}, None
        else:
            print(
                f"✅ {source}: Usando fallback con {len(fallback_snapshots)} registros"
            )

            # Agrupar por currency y tomar el más reciente de cada uno
            latest_by_currency: dict[str, RateSnapshot] = {}
            for snap in fallback_snapshots:
                if snap.currency not in latest_by_currency:
                    latest_by_currency[snap.currency] = snap

            snapshots = list(latest_by_currency.values())

    # Calcular edad de datos
    updated_at = snapshots[0].fetched_at
    data_age = now - updated_at
    age_minutes = int(data_age.total_seconds() / 60)

    if age_minutes > max_age_minutes:
        print(f"⚠️ {source}: Datos con {age_minutes}min de antigüedad (stale)")
    else:
        print(f"✅ {source}: Datos frescos ({age_minutes}min)")

    # Formatear datos - NUNCA retornar None
    formatted = {}

    for snap in snapshots:
        if source in ["eltoque", "binance", "bcc"]:
            # Validar que sell_rate no sea None
            if snap.sell_rate is None:
                print(f"⚠️ {source}/{snap.currency}: sell_rate es None, saltando")
                continue

            rate = float(snap.sell_rate)
            prev_rate = await _get_previous_snapshot(
                session, source, snap.currency, snap.fetched_at
            )
            formatted[snap.currency] = {
                "rate": rate,
                "change": calculate_change(rate, prev_rate),
                "prev_rate": prev_rate,
            }

        elif source == "cadeca":
            # CADECA necesita al menos buy_rate o sell_rate
            if snap.buy_rate is None and snap.sell_rate is None:
                print(
                    f"⚠️ {source}/{snap.currency}: buy_rate y sell_rate son None, saltando"
                )
                continue

            prev_rate = None
            if snap.sell_rate:
                prev_rate = await _get_previous_snapshot(
                    session, source, snap.currency, snap.fetched_at
                )
            formatted[snap.currency] = {
                "buy": float(snap.buy_rate) if snap.buy_rate else None,
                "sell": float(snap.sell_rate) if snap.sell_rate else None,
                "change": calculate_change(
                    float(snap.sell_rate) if snap.sell_rate else 0, prev_rate
                ),
                "prev_rate": prev_rate,
            }

    if not formatted:
        print(f"⚠️ {source}: No se pudo formatear ningún dato válido")

    return formatted, updated_at


async def get_history(
    session: AsyncSession, source: str, currency: str, days: int
) -> list[RateSnapshot]:
    """
    Obtiene histórico de tasas para una fuente y moneda.

    Args:
        session: SQLAlchemy async session
        source: Fuente de datos
        currency: Moneda a consultar
        days: Días de histórico

    Returns:
        Lista de RateSnapshot ordenados por fetched_at desc
    """
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    stmt = (
        select(RateSnapshot)
        .where(
            RateSnapshot.source == source,
            RateSnapshot.currency == currency,
            RateSnapshot.fetched_at >= cutoff,
        )
        .order_by(RateSnapshot.fetched_at.desc())
    )

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def fetch_cubanomic_daily(db: AsyncSession) -> dict:
    """
    Fetch Cubanomic data daily and save to database.

    Steps:
    1. Call scraper fetch_cubanomic()
    2. Save latest rates to DB (CubanomicRate)
    3. Save all historical data points (RateSnapshot)
    4. Return result dict

    Args:
        db: AsyncSession database session

    Returns:
        dict with format:
        {
            "ok": True,
            "rates_saved": 3,  # USD, EUR, MLC
            "history_saved": 90,  # Total historical points
            "updated_at": "2026-03-28T00:00:00Z"
        }
        Or error:
        {
            "ok": False,
            "error": "Error message"
        }
    """
    try:
        # Fetch data from Cubanomic API
        result = await fetch_cubanomic(days=30)

        if not result.get("ok"):
            error_msg = result.get("error", {}).get("message", "Unknown error")
            print(f"❌ 🇨🇺 Cubanomic fetch failed: {error_msg}")
            return {"ok": False, "error": error_msg}

        data = result.get("data", {})
        history = result.get("history", [])
        updated_at = result.get("updated_at")

        # Parse rates
        usd_rate = data.get("USD", {}).get("rate")
        eur_rate = data.get("EUR", {}).get("rate")
        mlc_rate = data.get("MLC", {}).get("rate")

        if not all([usd_rate, eur_rate, mlc_rate]):
            print(f"❌ 🇨🇺 Cubanomic: Missing required rates")
            return {"ok": False, "error": "Missing required rates"}

        # Parse updated_at timestamp
        try:
            fetched_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            fetched_at = datetime.now(timezone.utc)

        # Save snapshot
        await save_cubanomic_snapshot(db, usd_rate, eur_rate, mlc_rate, fetched_at)
        print(f"✅ 🇨🇺 Cubanomic snapshot saved: USD={usd_rate}, EUR={eur_rate}, MLC={mlc_rate}")

        # Save historical data points
        history_count = 0
        if history:
            now = datetime.now(timezone.utc)
            snapshots = []

            for point in history:
                currency = point.get("currency")
                rate = point.get("rate")
                date_str = point.get("date")

                if not all([currency, rate, date_str]):
                    continue

                # Parse date string to datetime
                try:
                    point_date = datetime.fromisoformat(date_str)
                    if point_date.tzinfo is None:
                        point_date = point_date.replace(tzinfo=timezone.utc)
                except (ValueError, AttributeError):
                    point_date = now

                snapshot = RateSnapshot(
                    source="cubanomic",
                    currency=currency,
                    buy_rate=None,
                    sell_rate=float(rate),
                    fetched_at=point_date,
                )
                snapshots.append(snapshot)

            if snapshots:
                db.add_all(snapshots)
                history_count = len(snapshots)
                print(f"✅ 🇨🇺 Cubanomic history saved: {history_count} points")

        await db.commit()

        return {
            "ok": True,
            "rates_saved": 3,
            "history_saved": history_count,
            "updated_at": updated_at,
        }

    except Exception as e:
        print(f"❌ 🇨🇺 Cubanomic fetch error: {e}")
        await db.rollback()
        return {"ok": False, "error": str(e)}


async def save_cubanomic_snapshot(
    db: AsyncSession,
    usd_rate: float,
    eur_rate: float,
    mlc_rate: float,
    fetched_at: datetime
) -> None:
    """
    Create and save CubanomicRate record.

    Args:
        db: AsyncSession database session
        usd_rate: USD exchange rate
        eur_rate: EUR exchange rate
        mlc_rate: MLC exchange rate
        fetched_at: Timestamp of the data
    """
    snapshot = CubanomicRate(
        usd_rate=float(usd_rate),
        eur_rate=float(eur_rate),
        mlc_rate=float(mlc_rate),
        fetched_at=fetched_at,
    )
    db.add(snapshot)
    print(f"✅ 🇨🇺 CubanomicRate created: {snapshot}")


async def get_cubanomic_cached(
    db: AsyncSession,
    redis_client: "RedisClient"
) -> dict:
    """
    Get Cubanomic data with Redis cache.
    Cache TTL: 24 hours (86400 seconds).

    Returns cached data if available, otherwise fetches fresh data.
    Only caches successful results with actual data (not empty/error responses).

    Args:
        db: AsyncSession database session
        redis_client: Redis client instance

    Returns:
        dict with format:
        {
            "ok": True,
            "data": {...},
            "updated_at": "2026-03-28T00:00:00Z"
        }
        Or error:
        {
            "ok": False,
            "error": "Error message"
        }
    """
    cache_key = "cubanomic:latest"

    # Try cache first
    cached = await redis_client.get(cache_key)
    if cached:
        logger.info("♻️ Cubanomic cache HIT")
        # Parse cached JSON string back to dict
        import json
        cached_data = json.loads(cached)

        # Only return cached data if it has actual rates (not empty/error)
        if cached_data.get("ok") and cached_data.get("data"):
            return cached_data

        # Cache is empty or error, delete it and fetch fresh
        logger.info("⚠️ Cubanomic cache has empty/error data, deleting...")
        await redis_client.delete(cache_key)

    # Fetch fresh data
    logger.info("🔍 Cubanomic cache MISS, fetching...")
    result = await fetch_cubanomic_daily(db)

    if result.get("ok") and result.get("data"):
        # Only cache successful results with data
        import json
        await redis_client.set(cache_key, json.dumps(result), ttl=86400)
        logger.info("✅ Cubanomic data cached for 24h")
    else:
        logger.warning(f"⚠️ Cubanomic fetch returned empty/error result, not caching: {result}")

    return result


async def save_history_snapshot(db: AsyncSession, rates_data: dict) -> None:
    """
    Save a snapshot of all rates to the history_snapshots table.
    Called automatically by the scheduler every 5 minutes.

    Args:
        db: AsyncSession database session
        rates_data: dict with format from fetch_all_sources()
    """
    from src.models.rates import HistorySnapshot
    from datetime import datetime

    snapshot = HistorySnapshot(
        fetched_at=datetime.now(timezone.utc),
        # ElToque
        eltoque_usd=rates_data.get('eltoque', {}).get('USD', {}).get('rate'),
        eltoque_eur=rates_data.get('eltoque', {}).get('EUR', {}).get('rate'),
        eltoque_mlc=rates_data.get('eltoque', {}).get('MLC', {}).get('rate'),
        # CADECA (average of buy/sell)
        cadeca_usd=_average_cadeca_rate(rates_data.get('cadeca', {}).get('USD', {})),
        cadeca_eur=_average_cadeca_rate(rates_data.get('cadeca', {}).get('EUR', {})),
        cadeca_mlc=_average_cadeca_rate(rates_data.get('cadeca', {}).get('MLC', {})),
        # BCC (average of buy/sell)
        bcc_usd=_average_cadeca_rate(rates_data.get('bcc', {}).get('USD', {})),
        bcc_eur=_average_cadeca_rate(rates_data.get('bcc', {}).get('EUR', {})),
        bcc_mlc=_average_cadeca_rate(rates_data.get('bcc', {}).get('MLC', {})),
        # Binance
        binance_btc=rates_data.get('binance', {}).get('BTC', {}).get('rate'),
        binance_eth=rates_data.get('binance', {}).get('ETH', {}).get('rate'),
    )

    db.add(snapshot)
    await db.commit()
    logger.info(f"📊 History snapshot saved: {snapshot.fetched_at}")


def _average_cadeca_rate(rate_data: dict | float) -> float | None:
    """Calculate average of buy/sell rates for CADECA/BCC.
    
    Args:
        rate_data: Can be dict {'buy': float, 'sell': float} or float directly
    """
    if not rate_data:
        return None
    
    # BCC returns float directly, CADECA returns dict
    if isinstance(rate_data, (int, float)):
        return float(rate_data)
    
    # CADECA format: {'buy': float, 'sell': float}
    buy = rate_data.get('buy')
    sell = rate_data.get('sell')
    if buy and sell:
        return (buy + sell) / 2
    return buy or sell
