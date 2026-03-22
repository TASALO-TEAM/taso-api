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

ChangeDirection = Literal['up', 'down', 'neutral']


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
        return 'neutral'
    
    difference = current - previous
    
    if difference > CHANGE_TOLERANCE:
        return 'up'
    elif difference < -CHANGE_TOLERANCE:
        return 'down'
    else:
        return 'neutral'


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
        return_exceptions=False
    )
    
    return {
        'eltoque': results[0],
        'binance': results[1],
        'cadeca': results[2],
        'bcc': results[3]
    }


def _normalize_eltoque_data(data: dict) -> list[dict]:
    """
    Normaliza datos de ElToque a lista de {currency, buy_rate, sell_rate}.
    
    Legacy: estructura de legacy/tasa.py -> tasas_actuales
    """
    tasas = data.get('tasas', {})
    result = []
    
    for currency, rate in tasas.items():
        # ElToque usa tasa única (venta)
        result.append({
            'currency': 'USDT' if currency == 'USDT_TRC20' else currency,
            'buy_rate': None,  # ElToque no tiene compra
            'sell_rate': float(rate)
        })
    
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
            result.append({
                'currency': currency,
                'buy_rate': float(value.get('compra', 0)),
                'sell_rate': float(value.get('venta', 0))
            })
        else:
            # BCC format (single rate)
            result.append({
                'currency': currency,
                'buy_rate': None,
                'sell_rate': float(value)
            })
    
    return result


def _normalize_binance_data(data: dict) -> list[dict]:
    """
    Normaliza datos de Binance a lista de {currency, buy_rate, sell_rate}.
    
    Binance: {'BTCUSDT': '45000.00', 'ETHUSDT': '2500.00'}
    """
    result = []
    
    for symbol, price in data.items():
        # Extraer currency del símbolo (BTCUSDT -> BTC)
        currency = symbol.replace('USDT', '')
        result.append({
            'currency': currency,
            'buy_rate': None,
            'sell_rate': float(price)
        })
    
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
    if source == 'eltoque':
        normalized = _normalize_eltoque_data(data)
    elif source == 'cadeca':
        normalized = _normalize_cadeca_bcc_data(data, source)
    elif source == 'bcc':
        normalized = _normalize_cadeca_bcc_data(data, source)
    elif source == 'binance':
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
            currency=item['currency'],
            buy_rate=item['buy_rate'],
            sell_rate=item['sell_rate'],
            fetched_at=now
        )
        snapshots.append(snapshot)
    
    session.add_all(snapshots)
    print(f"✅ Guardados {len(snapshots)} snapshots de {source}")


async def _get_previous_snapshot(
    session: AsyncSession,
    source: str,
    currency: str,
    current_fetched_at: datetime
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
            RateSnapshot.fetched_at < current_fetched_at
        )
        .order_by(RateSnapshot.fetched_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.first()
    return float(row[0]) if row and row[0] else None


async def get_latest_rates(session: AsyncSession) -> dict[str, dict]:
    """
    Obtiene el snapshot más reciente de cada fuente.

    Returns:
        dict con estructura:
        {
            'eltoque': {'USD': {'rate': 365.0, 'change': 'up'}},
            'binance': {'BTC': {'rate': 45000.0}},
            'cadeca': {'USD': {'buy': 120.0, 'sell': 125.0}},
            'bcc': {'USD': {'rate': 125.0}}
        }
    """
    result = {}

    for source in ['eltoque', 'binance', 'cadeca', 'bcc']:
        # Subquery para obtener el fetched_at más reciente por fuente
        subquery = (
            select(func.max(RateSnapshot.fetched_at))
            .where(RateSnapshot.source == source)
            .scalar_subquery()
        )

        # Obtener todos los registros con ese fetched_at
        stmt = select(RateSnapshot).where(
            RateSnapshot.source == source,
            RateSnapshot.fetched_at == subquery
        )

        query_result = await session.execute(stmt)
        snapshots = query_result.scalars().all()

        if not snapshots:
            result[source] = {}
            continue

        # Formatear según fuente
        if source == 'eltoque' or source == 'binance' or source == 'bcc':
            formatted = {}
            for snap in snapshots:
                rate = snap.sell_rate  # Usar sell_rate como principal
                if rate:
                    # Obtener tasa anterior para calcular cambio
                    prev_rate = await _get_previous_snapshot(
                        session, source, snap.currency, snap.fetched_at
                    )
                    formatted[snap.currency] = {
                        'rate': float(rate),
                        'change': calculate_change(float(rate), prev_rate),
                        'prev_rate': prev_rate,
                        'fetched_at': snap.fetched_at.isoformat()
                    }
            result[source] = formatted

        elif source == 'cadeca':
            formatted = {}
            for snap in snapshots:
                if snap.buy_rate or snap.sell_rate:
                    # Obtener tasa anterior para calcular cambio (usar sell_rate)
                    prev_rate = None
                    if snap.sell_rate:
                        prev_rate = await _get_previous_snapshot(
                            session, source, snap.currency, snap.fetched_at
                        )
                    formatted[snap.currency] = {
                        'buy': float(snap.buy_rate) if snap.buy_rate else None,
                        'sell': float(snap.sell_rate) if snap.sell_rate else None,
                        'change': calculate_change(
                            float(snap.sell_rate) if snap.sell_rate else 0,
                            prev_rate
                        ),
                        'prev_rate': prev_rate,
                        'fetched_at': snap.fetched_at.isoformat()
                    }
            result[source] = formatted

    return result


async def get_source_rates(
    session: AsyncSession,
    source: str
) -> tuple[dict[str, dict], datetime | None]:
    """
    Obtiene tasas de una fuente específica con cambio calculado.

    Args:
        session: SQLAlchemy async session
        source: 'eltoque' | 'cadeca' | 'bcc' | 'binance'

    Returns:
        Tupla con (dict de tasas, timestamp actualizado)
    """
    subquery = (
        select(func.max(RateSnapshot.fetched_at))
        .where(RateSnapshot.source == source)
        .scalar_subquery()
    )

    stmt = select(RateSnapshot).where(
        RateSnapshot.source == source,
        RateSnapshot.fetched_at == subquery
    )

    query_result = await session.execute(stmt)
    snapshots = query_result.scalars().all()

    if not snapshots:
        return {}, None

    formatted = {}
    updated_at = snapshots[0].fetched_at

    for snap in snapshots:
        if source in ['eltoque', 'binance', 'bcc']:
            rate = snap.sell_rate
            if rate:
                prev_rate = await _get_previous_snapshot(
                    session, source, snap.currency, snap.fetched_at
                )
                formatted[snap.currency] = {
                    'rate': float(rate),
                    'change': calculate_change(float(rate), prev_rate),
                    'prev_rate': prev_rate
                }
        elif source == 'cadeca':
            if snap.buy_rate or snap.sell_rate:
                prev_rate = None
                if snap.sell_rate:
                    prev_rate = await _get_previous_snapshot(
                        session, source, snap.currency, snap.fetched_at
                    )
                formatted[snap.currency] = {
                    'buy': float(snap.buy_rate) if snap.buy_rate else None,
                    'sell': float(snap.sell_rate) if snap.sell_rate else None,
                    'change': calculate_change(
                        float(snap.sell_rate) if snap.sell_rate else 0,
                        prev_rate
                    ),
                    'prev_rate': prev_rate
                }

    return formatted, updated_at


async def get_history(
    session: AsyncSession,
    source: str,
    currency: str,
    days: int
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
            RateSnapshot.fetched_at >= cutoff
        )
        .order_by(RateSnapshot.fetched_at.desc())
    )

    result = await session.execute(stmt)
    return list(result.scalars().all())
