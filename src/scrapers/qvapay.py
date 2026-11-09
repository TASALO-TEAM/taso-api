"""Scraper de la API pública P2P de QvaPay (promedios de compra/venta por método de pago).

Además de las monedas fijas de QVAPAY_COINS, descubre solas las que QvaPay vaya activando: lee su lista pública
`coins/v2`, sondea las candidatas de a pocas por ciclo (QvaPay responde 429 si se piden muchas seguidas) y las que
traen operaciones pasan a consultarse en cada ciclo. Los datos descriptivos (nombre, tipo, operaciones) se exponen con
`qvapay_meta` para que los clientes (app, bot) no necesiten conocer de antemano cada moneda.
"""

import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

QVAPAY_URL = "https://api.qvapay.com/p2p/completed_pairs_average"
QVAPAY_COINS_URL = "https://api.qvapay.com/coins/v2"
DEFAULT_TIMEOUT = 8.0

# Etiqueta pública -> código de moneda de la API de QvaPay.
# Las etiquetas son las mismas que usa el comando /qp del bot, para que bot, API y app
# hablen igual. El orden del dict es el orden de aparición.
QVAPAY_COINS: Dict[str, str] = {
    "CUP": "BANK_CUP",
    "MLC": "BANK_MLC",
    "TROPIPAY": "TROPIPAY",
    "ETECSA": "ETECSA",
    "ZELLE": "ZELLE",
    "CLASICA": "CLASICA",
    "BOLSATM": "BOLSATM",
    "BANDECPREPAGO": "BANDECPREPAGO",
    "SBERBANK": "SBERBANK",
    "CUPCASH": "CUPCASH",  # CUP en efectivo (categoría Cash); pocas operaciones, ventana de hasta 168 h
}

# --- Descubrimiento automático -------------------------------------------------------------------------------------
# Categorías de coins/v2 que son métodos de pago (el resto son criptomonedas): 2 banco, 3 efectivo, 4 billetera.
KINDS: Dict[int, str] = {2: "bank", 3: "cash", 4: "wallet"}
# Valen "1 USD por cada USD": no aportan una tasa.
EXCLUDED_CODES = {"BANK", "BANK_INTL"}
CATALOG_TTL = 6 * 3600  # la lista de monedas cambia rara vez: se lee cada 6 h (1 petición)
CATALOG_RETRY = 600  # si falla, se reintenta en 10 min
EXTRA_TTL = 7 * 24 * 3600  # una moneda descubierta sin datos durante 7 días vuelve a ser candidata
PROBE_PER_CYCLE = 4  # candidatas sondeadas por ciclo (~15 min): se recorren todas en unas 2-3 h sin provocar 429
PROBE_GAP = 1.0  # segundos entre sondeos
MAINTENANCE_BUDGET = 8.0  # tope de segundos del mantenimiento: nunca retrasa el ciclo de tasas
_MAX_NAME = 40

_catalog: Dict[str, Dict[str, Any]] = {}  # código -> {"name", "kind", "p2p"}
_catalog_next_at: float = 0.0
_extras: Dict[str, float] = {}  # código descubierto -> última vez que tuvo datos
_counts: Dict[str, int] = {}  # código -> operaciones detrás del último promedio
_probe_cursor: int = 0


def reset_state() -> None:
    """Vacía lo descubierto (para pruebas y para forzar un redescubrimiento)."""
    global _catalog, _catalog_next_at, _extras, _counts, _probe_cursor
    _catalog, _catalog_next_at, _extras, _counts, _probe_cursor = {}, 0.0, {}, {}, 0


def _to_float(value) -> Optional[float]:
    """Convierte a float; None si el valor falta, no es numérico o no es positivo."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _to_count(value) -> Optional[int]:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _clean_name(value: Any, fallback: str) -> str:
    """Nombre legible que viene de QvaPay: sin caracteres de control ni espacios de más, y de largo acotado."""
    text = re.sub(r"[\x00-\x1f\x7f]", "", str(value or "")).strip()
    text = re.sub(r"\s+", " ", text)[:_MAX_NAME].strip()
    return text or fallback


async def _fetch_coin(
    client: httpx.AsyncClient, coin_code: str
) -> Optional[Dict[str, Optional[float]]]:
    """Consulta una moneda. Devuelve {"buy": x, "sell": y} o None si no hay datos.

    Anota de paso cuántas operaciones respaldan el promedio (`count`).
    Nunca lanza: un fallo de una moneda no debe tumbar las demás.
    """
    try:
        response = await client.get(QVAPAY_URL, params={"coin": coin_code})
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return None
        buy = _to_float(data.get("average_buy"))
        sell = _to_float(data.get("average_sell"))
        if buy is None and sell is None:
            logger.info("QvaPay %s: sin operaciones recientes", coin_code)
            return None
        count = _to_count(data.get("count"))
        if count is not None:
            _counts[coin_code] = count
        return {"buy": buy, "sell": sell}
    except (httpx.TimeoutException, httpx.NetworkError) as e:
        logger.warning("QvaPay %s: error de red: %s", coin_code, e)
        return None
    except httpx.HTTPStatusError as e:
        logger.warning("QvaPay %s: HTTP %s", coin_code, e.response.status_code)
        return None
    except Exception as e:  # JSON inválido u otro error inesperado
        logger.warning("QvaPay %s: error inesperado: %s", coin_code, e)
        return None


async def _refresh_catalog(client: httpx.AsyncClient) -> None:
    """Lee `coins/v2` (una petición cada CATALOG_TTL). Nunca lanza."""
    global _catalog, _catalog_next_at
    now = time.time()
    if now < _catalog_next_at:
        return
    try:
        response = await client.get(QVAPAY_COINS_URL)
        response.raise_for_status()
        data = response.json()
        catalog: Dict[str, Dict[str, Any]] = {}
        for item in data if isinstance(data, list) else []:
            if not isinstance(item, dict):
                continue
            code = item.get("tick")
            kind = KINDS.get(item.get("coins_categories_id"))
            if not isinstance(code, str) or not code or kind is None:
                continue
            catalog[code] = {
                "name": _clean_name(item.get("name"), code),
                "kind": kind,
                "p2p": bool(item.get("enabled_p2p")),
            }
        if catalog:
            _catalog = catalog
            _catalog_next_at = now + CATALOG_TTL
        else:
            _catalog_next_at = now + CATALOG_RETRY
    except Exception as e:
        logger.warning("QvaPay coins/v2: %s", e)
        _catalog_next_at = now + CATALOG_RETRY


def _candidates() -> List[str]:
    known = set(QVAPAY_COINS.values())
    return sorted(
        code
        for code, info in _catalog.items()
        if info["p2p"] and code not in known and code not in _extras and code not in EXCLUDED_CODES
    )


async def _discover(timeout: float) -> None:
    """Refresca la lista de monedas y sondea unas pocas candidatas; las que traen datos pasan a `_extras`."""
    global _probe_cursor
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=4.0)) as client:
        await _refresh_catalog(client)
        candidates = _candidates()
        if not candidates:
            return
        for i in range(min(PROBE_PER_CYCLE, len(candidates))):
            code = candidates[(_probe_cursor + i) % len(candidates)]
            if await _fetch_coin(client, code) is not None:
                _extras[code] = time.time()
                logger.info("QvaPay: moneda nueva con operaciones: %s", code)
            await asyncio.sleep(PROBE_GAP)
        _probe_cursor = (_probe_cursor + PROBE_PER_CYCLE) % len(candidates)


async def _discover_safe(timeout: float) -> None:
    try:
        await asyncio.wait_for(_discover(timeout), MAINTENANCE_BUDGET)
    except asyncio.TimeoutError:
        logger.info("QvaPay: el descubrimiento de monedas no terminó a tiempo; sigue en el próximo ciclo")
    except Exception as e:
        logger.warning("QvaPay: error en el descubrimiento de monedas: %s", e)


def qvapay_meta(label: str) -> Dict[str, Any]:
    """Datos descriptivos de una moneda de QvaPay: {"name", "kind", "count"} (solo las claves que se conocen)."""
    code = QVAPAY_COINS.get(label, label)
    meta: Dict[str, Any] = {}
    info = _catalog.get(code)
    if info:
        meta["name"] = info["name"]
        meta["kind"] = info["kind"]
    if code in _counts:
        meta["count"] = _counts[code]
    return meta


async def fetch_qvapay(
    timeout: float = DEFAULT_TIMEOUT,
) -> Optional[Dict[str, Dict[str, Optional[float]]]]:
    """
    Obtiene los promedios P2P de QvaPay para todos los métodos de pago.

    Cada valor es "cuánto de ese método por 1 USD de QvaPay" (no son todos CUP por unidad).
    Consulta en paralelo las monedas de QVAPAY_COINS más las descubiertas automáticamente (etiqueta = código de
    QvaPay) y omite las que no tienen datos (p. ej. SBERBANK casi siempre). Mientras tanto sondea unas pocas
    candidatas nuevas (ver `_discover`).

    Returns:
        {etiqueta: {"buy": average_buy | None, "sell": average_sell | None}}, o None si
        no respondió ninguna moneda.
    """
    coins: Dict[str, str] = dict(QVAPAY_COINS)
    for code in list(_extras):
        coins.setdefault(code, code)
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=4.0)
        ) as client:
            results, _ = await asyncio.gather(
                asyncio.gather(*(_fetch_coin(client, code) for code in coins.values())),
                _discover_safe(timeout),
            )
    except Exception as e:
        logger.warning("QvaPay: error inesperado: %s", e)
        return None

    now = time.time()
    for (label, code), value in zip(coins.items(), results):
        if code not in _extras:
            continue
        if value is not None:
            _extras[code] = now
        elif now - _extras[code] > EXTRA_TTL:
            _extras.pop(code, None)
            _counts.pop(code, None)

    rates = {
        label: value
        for label, value in zip(coins.keys(), results)
        if value is not None
    }
    return rates or None
