"""Rates business logic service."""

import asyncio
from typing import Any
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.scrapers.eltoque import fetch_eltoque
from src.scrapers.binance import fetch_binance
from src.scrapers.cadeca import fetch_cadeca
from src.scrapers.bcc import fetch_bcc
from src.models.rate_snapshot import RateSnapshot


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
