"""Cubanomic LIVE rates scraper (backup for ElToque API).

Usa el endpoint real de tasas en vivo que alimenta iframe.cubanomic.com.
Requiere header Referer para que el token sea aceptado.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

CUBANOMIC_TOKEN = "hRaCcY78gXC3k9WRv01pR7V1fgSxlg"
CUBANOMIC_API_URL = "https://api.cubanomic.com/api/v1/x-rates"
REFERER = "https://iframe.cubanomic.com/"

CURRENCY_MAP = {
    "ECU": "EUR",
    "USDT_TRC20": "USDT",
    "USDT": "USDT",
}


async def fetch_cubanomic_live(
    timeout: float = 12.0,
    hours_back: int = 24,
) -> Optional[dict[str, Any]]:
    """
    Obtiene las tasas en vivo desde Cubanomic (respaldo de ElToque).

    Returns formato compatible con ElToque:
    {
        "tasas": {"USD": 925.0, "EUR": 1000.0, "MLC": 837.59, ...},
        "date": "2026-11-17",
        "hour": 14,
        "minutes": 5,
        "seconds": 23,
        "source": "cubanomic_live"
    }
    o None si falla.
    """
    now = datetime.now(timezone.utc)
    date_to = now.strftime("%Y-%m-%d %H:%M:%S")
    date_from = (now - timedelta(hours=hours_back)).strftime("%Y-%m-%d %H:%M:%S")

    params = {
        "msg": "false",
        "date_from": date_from,
        "date_to": date_to,
        "token": CUBANOMIC_TOKEN,
    }

    headers = {
        "Accept": "application/json",
        "Referer": REFERER,
        "Origin": "https://iframe.cubanomic.com",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                CUBANOMIC_API_URL,
                params=params,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            raw = response.json()

        return _normalize_to_eltoque_format(raw)

    except httpx.HTTPStatusError as e:
        logger.warning(f"Cubanomic live HTTP {e.response.status_code}: {e}")
        return None
    except httpx.TimeoutException:
        logger.warning("Cubanomic live timeout")
        return None
    except Exception as e:
        logger.error(f"Cubanomic live unexpected error: {e}")
        return None


def _normalize_to_eltoque_format(raw: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Convierte la respuesta de Cubanomic al formato que espera el resto del sistema."""
    try:
        stats = raw.get("statistics") or {}
        if not stats:
            return None

        tasas: dict[str, float] = {}

        for key, info in stats.items():
            if not isinstance(info, dict):
                continue

            clean_key = key.split(".")[0].upper()
            mapped = CURRENCY_MAP.get(clean_key, clean_key)

            median = info.get("median")
            if median is None:
                continue

            try:
                rate = float(median)
                if mapped not in tasas or rate > tasas[mapped]:
                    tasas[mapped] = rate
            except (TypeError, ValueError):
                continue

        if not tasas:
            return None

        return {
            "tasas": tasas,
            "date": raw.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "hour": raw.get("hour", 0),
            "minutes": raw.get("minutes", 0),
            "seconds": raw.get("seconds", 0),
            "source": "cubanomic_live",
        }

    except Exception as e:
        logger.error(f"Error normalizando Cubanomic: {e}")
        return None
