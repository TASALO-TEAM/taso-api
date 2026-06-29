"""ElToque fuel price scraper.

Scrapes the fuel section from eltoque.com, returning structured data for
each fuel type (B-94, B-90, B-83, Petróleo, Gas LP).
"""

from __future__ import annotations

import html
import json
import re
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ELTOQUE_FUEL_URL = "https://eltoque.com"
DEFAULT_TIMEOUT = 15.0


async def fetch_fuel(
    url: str = ELTOQUE_FUEL_URL,
    timeout: float = DEFAULT_TIMEOUT,
) -> Optional[dict[str, dict[str, Any]]]:
    """Fetch fuel prices from ElToque's fuel section.

    Returns a dict keyed by fuel name, e.g.::

        {
            "B-94": {
                "subtype": "Especial",
                "range_min": 3200.0,
                "range_max": 4710.0,
                "unit": "CUP/L",
                "change_pct": -2.5,
                "change_direction": "down",
            },
            ...
        }

    Returns ``None`` on any failure (HTTP error, timeout, parse error).
    """
    try:
        async with httpx.AsyncClient(verify=False, timeout=timeout) as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
                },
            )
            response.raise_for_status()
    except httpx.HTTPStatusError:
        return None
    except httpx.ReadTimeout:
        return None
    except httpx.ConnectTimeout:
        return None
    except httpx.RequestError:
        return None
    except Exception:
        return None

    try:
        soup = BeautifulSoup(response.text, "html.parser")
        results = _parse_fuel_items(soup)
        return results if results else None
    except Exception:
        return None


def _parse_fuel_items(soup: BeautifulSoup) -> dict[str, dict[str, Any]]:
    """Extract fuel items from the fuel list container.

    Robustness strategy: look for ``role="list"`` containers and then
    iterate over ``role="listitem"`` children.  For each item we try to
    read the fuel name, subtype, price/range, unit and change indicator.
    """
    data: dict[str, dict[str, Any]] = {}

    list_containers = soup.find_all("div", attrs={"role": "list"})
    target_container = None
    for container in list_containers:
        items = container.find_all("div", attrs={"role": "listitem"})
        if not items:
            continue
        texts = " ".join(item.get_text(" ", strip=True) for item in items)
        if any(token in texts for token in ("B-94", "B-90", "B-83", "Gas LP", "Petróleo")):
            target_container = container
            break

    if target_container is None:
        return data

    for item in target_container.find_all("div", attrs={"role": "listitem"}):
        text = item.get_text(" ", strip=True)
        if not any(token in text for token in ("B-94", "B-90", "B-83", "Gas LP", "Petróleo")):
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

        # Normalize key to a stable identifier
        data[name] = record

    return data


def _extract_fuel_name(item: Any, fallback_text: str) -> str | None:
    """Return a normalized fuel name from the primary heading div."""
    heading = item.find(
        "div",
        style=lambda v: v and "font-weight: 600" in v and "font-size" in v,
    )
    if heading:
        raw = heading.get_text(strip=True)
        if raw:
            return _normalize_name(raw)

    # Fallback: first token in item text
    first = fallback_text.split()[0]
    return _normalize_name(first)


def _normalize_name(raw: str) -> str:
    raw = raw.strip()
    if raw in ("B-94", "B-90", "B-83"):
        return raw
    if raw in ("Petróleo", "Petroleo", "Diésel", "Diesel"):
        return "Petroleo"
    if raw in ("Gas LP", "Gas", "LP"):
        return "Gas_LP"
    return raw


def _extract_subtype(item: Any) -> str | None:
    """Extract subtype (e.g. Especial, Regular, Motor, Diésel, Balón)."""
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
    """Extract numeric prices and unit from the price area."""
    price_div = item.find(
        "div",
        style=lambda v: v and "align-items: flex-end" in v,
    )
    if not price_div:
        return

    full_text = price_div.get_text(" ", strip=True)
    # Match numeric tokens (allow thousand separators and decimals)
    numbers = re.findall(r"[\d]+(?:\.[\d]+)?", full_text)
    if not numbers:
        return

    floats = [float(n) for n in numbers]

    # Detect unit
    if "CUP/balón" in full_text or "balón" in full_text.lower():
        record["unit"] = "CUP/balón"

    if len(floats) >= 2:
        record["range_min"] = floats[0]
        record["range_max"] = floats[1]
    elif len(floats) == 1:
        record["range_min"] = floats[0]
        record["range_max"] = floats[0]


def _extract_change(item: Any, record: dict[str, Any]) -> None:
    """Extract percentage change and direction."""
    change_span = item.find(
        "span",
        style=lambda v: v and "color: rgb(31, 122, 58)" in v,
    )
    if not change_span:
        return

    text = change_span.get_text(strip=True)
    if not text:
        return

    # Direction
    if "▼" in text:
        record["change_direction"] = "down"
    elif "▲" in text:
        record["change_direction"] = "up"

    # Percentage
    m = re.search(r"(-?[\d]+(?:\.[\d]+)?)\s*%", text)
    if m:
        try:
            record["change_pct"] = float(m.group(1))
        except ValueError:
            pass
