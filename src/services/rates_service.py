"""Rates business logic service."""

import asyncio
from typing import Any, Literal
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.scrapers.eltoque import fetch_eltoque
from src.scrapers.binance import fetch_binance
from src.scrapers.cadeca import fetch_cadeca
from src.scrapers.bcc import fetch_bcc
from src.models.rate_snapshot import RateSnapshot


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
