"""ElToque fuel price scraper.

Estrategia: extrae datos del bloque __NEXT_DATA__ (JSON embebido por Next.js)
en la página principal de eltoque.com. No requiere JS, Playwright ni Selenium.

Los datos están en:
  props.pageProps.fuelPrices.items[]

Estructura de cada item:
  {
    "fuel": "B94",
    "label": "B-94",
    "subtitle": "Especial",
    "stats": {"min": 3000, "max": 7367, "median": 3900},
    "previous": {"median": 4000},
    "delta": {"median_pct": -2.5},
    "display": {"range_min": 3200, "range_max": 4710, "primary_value": 3900}
  }
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

import httpx
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

ELTOQUE_URL = "https://eltoque.com"
DEFAULT_TIMEOUT = 20.0

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "identity",   # sin compresión — evita truncamiento en uvicorn
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}

# Mapeo de claves internas → nombre normalizado usado en taso
_FUEL_KEY_MAP = {
    "B94": "B-94",
    "B90": "B-90",
    "B83": "B-83",
    "Petroleo": "Petroleo",
    "PETROLEO": "Petroleo",
    "GAS_LP": "Gas_LP",
    "GASLP": "Gas_LP",
    "GasLP": "Gas_LP",
}


async def fetch_fuel(
    timeout: float = DEFAULT_TIMEOUT,
) -> Optional[dict[str, dict[str, Any]]]:
    """Obtiene precios de combustible de eltoque.com via __NEXT_DATA__.

    Returns:
        Dict keyed by nombre normalizado ("B-94", "B-90", etc.) con:
          - subtype: str
          - range_min, range_max: float
          - primary_value: float  (mediana)
          - unit: "CUP/L" o "CUP/balón"
          - change_pct: float | None
          - change_direction: "up" | "down" | "neutral"
        O None si falla.
    """
    html = await _fetch_html(timeout)
    if not html:
        logger.error("❌ [fuel] No se pudo obtener HTML de eltoque.com")
        return None

    next_data = _extract_next_data(html)
    if not next_data:
        logger.error("❌ [fuel] __NEXT_DATA__ no encontrado en el HTML (%d bytes)", len(html))
        return None

    fuel_prices = (
        next_data
        .get("props", {})
        .get("pageProps", {})
        .get("fuelPrices", {})
    )
    if not fuel_prices:
        logger.error("❌ [fuel] fuelPrices no encontrado en __NEXT_DATA__")
        return None

    items = fuel_prices.get("items", [])
    if not items:
        logger.warning("⚠️ [fuel] fuelPrices.items vacío")
        return None

    result = _parse_fuel_items(items)
    if result:
        window_to = fuel_prices.get("window_to", "")
        logger.info(
            "✅ [fuel] %d tipos de combustible obtenidos (window_to=%s)",
            len(result), window_to
        )
    return result if result else None


async def _fetch_html(timeout: float) -> Optional[str]:
    """Descarga el HTML de eltoque.com con headers de navegador."""
    try:
        async with httpx.AsyncClient(
            verify=False,
            timeout=timeout,
            follow_redirects=True,
        ) as client:
            resp = await client.get(ELTOQUE_URL, headers=_BROWSER_HEADERS)
            encoding = resp.headers.get("content-encoding", "none")
            logger.info(
                "🌐 [fuel] HTTP %d, size=%d bytes, encoding=%s",
                resp.status_code, len(resp.content), encoding,
            )
            if resp.status_code == 200:
                html = resp.text
                logger.debug("📄 [fuel] HTML text size: %d chars", len(html))
                return html
            logger.warning("⚠️ [fuel] HTTP %d para %s", resp.status_code, ELTOQUE_URL)
            return None
    except httpx.TimeoutException:
        logger.warning("⚠️ [fuel] Timeout al obtener HTML de eltoque.com")
        return None
    except Exception as e:
        logger.warning("⚠️ [fuel] Error obteniendo HTML: %s", e)
        return None


def _extract_next_data(html: str) -> Optional[dict]:
    """Extrae y parsea el bloque __NEXT_DATA__ del HTML."""
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as e:
        logger.error("❌ [fuel] Error parseando __NEXT_DATA__: %s", e)
        return None


def _parse_fuel_items(items: list) -> dict[str, dict[str, Any]]:
    """Convierte la lista de items de fuelPrices al formato interno de taso."""
    result: dict[str, dict[str, Any]] = {}

    for item in items:
        fuel_key = item.get("fuel", "")
        label = item.get("label", fuel_key)

        # Normalizar nombre
        normalized = _FUEL_KEY_MAP.get(fuel_key) or _FUEL_KEY_MAP.get(label)
        if not normalized:
            # Intentar normalizar manualmente
            clean = fuel_key.replace("-", "").replace("_", "").upper()
            if clean in ("B94",):
                normalized = "B-94"
            elif clean in ("B90",):
                normalized = "B-90"
            elif clean in ("B83",):
                normalized = "B-83"
            elif "PETROLEO" in clean or "DIESEL" in clean:
                normalized = "Petroleo"
            elif "GAS" in clean or "LP" in clean:
                normalized = "Gas_LP"
            else:
                logger.debug("⚠️ [fuel] Item ignorado: fuel=%s label=%s", fuel_key, label)
                continue

        display = item.get("display", {})
        delta = item.get("delta", {})
        previous = item.get("previous", {})

        range_min = display.get("range_min")
        range_max = display.get("range_max")
        primary = display.get("primary_value")

        # Si no hay display, usar stats
        if range_min is None:
            stats = item.get("stats", {})
            range_min = stats.get("min")
            range_max = stats.get("max")
            primary = stats.get("median")

        change_pct = delta.get("median_pct")
        if change_pct is not None:
            # eltoque usa negativo para bajada
            if change_pct < 0:
                direction = "down"
                change_pct = abs(change_pct)
            elif change_pct > 0:
                direction = "up"
            else:
                direction = "neutral"
        else:
            direction = "neutral"

        unit = "CUP/balón" if normalized == "Gas_LP" else "CUP/L"

        result[normalized] = {
            "subtype": item.get("subtitle"),
            "range_min": float(range_min) if range_min is not None else None,
            "range_max": float(range_max) if range_max is not None else None,
            "primary_value": float(primary) if primary is not None else None,
            "unit": unit,
            "change_pct": round(abs(change_pct), 2) if change_pct is not None else None,
            "change_direction": direction,
            "prev_median": float(previous.get("median")) if previous.get("median") else None,
        }

    return result
