"""ElToque fuel price scraper.

Estrategia de obtención de datos (en orden de prioridad):
  1. API JSON interna de ElToque (tasas.eltoque.com/v1/fuel o similar)
  2. Scrape de la sub-página /combustible con headers de navegador real
  3. Scrape de la página principal con múltiples User-Agents

eltoque.com es una SPA (Next.js). El HTML inicial que devuelve httpx
no contiene el DOM renderizado, por eso el parser original fallaba.
Esta versión intenta la API JSON primero (sin JS) y luego hace scrape
con técnicas anti-bot básicas.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

import httpx
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

ELTOQUE_API_FUEL_URLS = [
    "https://tasas.eltoque.com/v1/fuel",
    "https://tasas.eltoque.com/v1/combustible",
    "https://api.eltoque.com/v1/fuel",
]

ELTOQUE_SCRAPE_URLS = [
    "https://eltoque.com/combustible",
    "https://eltoque.com",
]

DEFAULT_TIMEOUT = 20.0

# Nombres de combustible que reconocemos en el HTML
FUEL_TOKENS = ("B-94", "B-90", "B-83", "Gas LP", "Petróleo", "Gasolina")

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}

_JSON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9",
    "Referer": "https://eltoque.com/",
    "Origin": "https://eltoque.com",
}


async def fetch_fuel(
    timeout: float = DEFAULT_TIMEOUT,
) -> Optional[dict[str, dict[str, Any]]]:
    """Obtiene precios de combustible de ElToque.

    Intenta en orden:
    1. API JSON interna de ElToque (más ligera, sin parsear HTML)
    2. Scrape de la sub-página /combustible
    3. Scrape de la página principal

    Returns:
        Dict con datos por tipo de combustible, o None si todo falla.
    """
    # Estrategia 1: API JSON interna
    result = await _try_json_api(timeout)
    if result:
        logger.info("✅ [fuel] Datos obtenidos via API JSON (estrategia 1)")
        return result

    # Estrategia 2 y 3: Scrape HTML
    from bs4 import BeautifulSoup
    for url in ELTOQUE_SCRAPE_URLS:
        html_text = await _fetch_html(url, timeout)
        if not html_text or len(html_text) < 500:
            logger.warning("⚠️ [fuel] HTML muy corto (%d bytes) de %s — posible Cloudflare challenge",
                           len(html_text) if html_text else 0, url)
            continue

        soup = BeautifulSoup(html_text, "html.parser")
        result = _parse_fuel_items(soup)
        if result:
            logger.info("✅ [fuel] Datos obtenidos via scrape HTML de %s", url)
            return result
        else:
            logger.warning("⚠️ [fuel] Parser no encontró datos en %s (HTML=%d bytes)",
                           url, len(html_text))

    logger.error("❌ [fuel] Todas las estrategias fallaron")
    return None


async def _try_json_api(timeout: float) -> Optional[dict[str, dict[str, Any]]]:
    """Intenta obtener datos de combustible de la API JSON de ElToque."""
    async with httpx.AsyncClient(verify=False, timeout=timeout, follow_redirects=True) as client:
        for url in ELTOQUE_API_FUEL_URLS:
            try:
                resp = await client.get(url, headers=_JSON_HEADERS)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                # Si la respuesta tiene estructura de combustible, parsearla
                parsed = _parse_json_response(data)
                if parsed:
                    return parsed
            except Exception as e:
                logger.debug("⚠️ [fuel] API %s falló: %s", url, e)
                continue
    return None


def _parse_json_response(data: Any) -> Optional[dict[str, dict[str, Any]]]:
    """Intenta extraer datos de combustible de una respuesta JSON de ElToque."""
    if not isinstance(data, dict):
        return None

    result: dict[str, dict[str, Any]] = {}

    # Buscar claves típicas de combustible en la respuesta
    for key in ("fuel", "combustible", "gasolina", "items"):
        items = data.get(key)
        if isinstance(items, list):
            for item in items:
                name = item.get("name") or item.get("type") or item.get("currency")
                if not name:
                    continue
                normalized = _normalize_name(name)
                if not normalized:
                    continue
                result[normalized] = {
                    "subtype": item.get("subtype") or item.get("label"),
                    "range_min": _to_float(item.get("min") or item.get("buy") or item.get("price")),
                    "range_max": _to_float(item.get("max") or item.get("sell") or item.get("price")),
                    "unit": item.get("unit", "CUP/L"),
                    "change_pct": _to_float(item.get("change_pct") or item.get("change")),
                    "change_direction": item.get("direction") or "neutral",
                }

    return result if result else None


async def _fetch_html(url: str, timeout: float) -> Optional[str]:
    """Descarga HTML de una URL con headers de navegador."""
    try:
        async with httpx.AsyncClient(
            verify=False,
            timeout=timeout,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url, headers=_BROWSER_HEADERS)
            if resp.status_code == 200:
                return resp.text
            logger.warning("⚠️ [fuel] HTTP %d para %s", resp.status_code, url)
            return None
    except httpx.TimeoutException:
        logger.warning("⚠️ [fuel] Timeout en %s", url)
        return None
    except Exception as e:
        logger.warning("⚠️ [fuel] Error en %s: %s", url, e)
        return None


def _parse_fuel_items(soup: Any) -> dict[str, dict[str, Any]]:
    """Extrae items de combustible del DOM renderizado.

    Busca el contenedor role="list" que tenga tokens de combustible.
    Solo funciona si el HTML incluye el DOM renderizado (no SPA pura).
    """
    data: dict[str, dict[str, Any]] = {}

    list_containers = soup.find_all("div", attrs={"role": "list"})
    target_container = None
    for container in list_containers:
        items = container.find_all("div", attrs={"role": "listitem"})
        if not items:
            continue
        texts = " ".join(item.get_text(" ", strip=True) for item in items)
        if any(token in texts for token in FUEL_TOKENS):
            target_container = container
            break

    if target_container is None:
        return data

    for item in target_container.find_all("div", attrs={"role": "listitem"}):
        text = item.get_text(" ", strip=True)
        if not any(token in text for token in FUEL_TOKENS):
            continue

        record: dict[str, Any] = {
            "subtype": _extract_subtype(item),
            "range_min": None,
            "range_max": None,
            "unit": "CUP/L",
            "change_pct": None,
            "change_direction": "neutral",
        }

        _extract_prices(item, record)
        _extract_change(item, record)

        name = _extract_fuel_name(item, text)
        if not name:
            continue

        data[name] = record

    return data


# ── Helpers de extracción HTML ────────────────────────────────────────────────

def _extract_fuel_name(item: Any, fallback_text: str) -> Optional[str]:
    heading = item.find(
        "div",
        style=lambda v: v and "font-weight: 600" in v and "font-size" in v,
    )
    if heading:
        raw = heading.get_text(strip=True)
        if raw:
            return _normalize_name(raw)
    first = fallback_text.split()[0]
    return _normalize_name(first)


def _normalize_name(raw: str) -> Optional[str]:
    raw = raw.strip()
    if raw in ("B-94", "B-90", "B-83"):
        return raw
    if raw in ("Petróleo", "Petroleo", "Diésel", "Diesel", "Gasolina"):
        return "Petroleo"
    if raw in ("Gas LP", "Gas", "LP", "GasLP"):
        return "Gas_LP"
    return None


def _extract_subtype(item: Any) -> Optional[str]:
    sub = item.find(
        "div",
        style=lambda v: v and "text-transform: uppercase" in v and "color: rgb(106, 115, 138)" in v,
    )
    if sub:
        text = sub.get_text(strip=True)
        if text:
            return text
    return None


def _extract_prices(item: Any, record: dict[str, Any]) -> None:
    price_div = item.find("div", style=lambda v: v and "align-items: flex-end" in v)
    if not price_div:
        return
    full_text = price_div.get_text(" ", strip=True)
    numbers = re.findall(r"[\d]+(?:\.[\d]+)?", full_text)
    if not numbers:
        return
    floats = [float(n) for n in numbers]
    if "CUP/balón" in full_text or "balón" in full_text.lower():
        record["unit"] = "CUP/balón"
    if len(floats) >= 2:
        record["range_min"] = floats[0]
        record["range_max"] = floats[1]
    elif len(floats) == 1:
        record["range_min"] = floats[0]
        record["range_max"] = floats[0]


def _extract_change(item: Any, record: dict[str, Any]) -> None:
    change_span = item.find("span", style=lambda v: v and "color: rgb(31, 122, 58)" in v)
    if not change_span:
        return
    text = change_span.get_text(strip=True)
    if not text:
        return
    if "▼" in text:
        record["change_direction"] = "down"
    elif "▲" in text:
        record["change_direction"] = "up"
    m = re.search(r"(-?[\d]+(?:\.[\d]+)?)\s*%", text)
    if m:
        try:
            record["change_pct"] = float(m.group(1))
        except ValueError:
            pass


def _to_float(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None
