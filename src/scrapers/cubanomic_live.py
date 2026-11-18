"""Cubanomic LIVE rates (respaldo y complemento de la API de ElToque).

Usa el endpoint real que alimenta iframe.cubanomic.com (no es scraping de HTML).
Requiere el header Referer para que el token sea aceptado.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)

CUBANOMIC_API_URL = "https://api.cubanomic.com/api/v1/x-rates"
REFERER = "https://iframe.cubanomic.com/"

# Cubanomic -> clave que usa el resto del sistema (misma convención que ElToque)
CURRENCY_MAP = {
    "ECU": "EUR",
    "USDT_TRC20": "USDT",
    "UDS": "ZELLE",  # Cubanomic publica Zelle (USD por transferencia en EE.UU.) como UDS
}

# CUP es la moneda base: Cubanomic la incluye en `statistics` pero no es una tasa de cambio.
EXCLUDED = {"CUP"}


async def fetch_cubanomic_live(
    timeout: float = 10.0,
    hours_back: int = 24,
    token: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Obtiene las tasas en vivo de Cubanomic en formato compatible con ElToque.

    Returns:
        {
          "tasas": {"USD": 930.0, "EUR": 1000.0, ...},
          "meta":  {"USD": {"messages": 389, "median_diff": 5.0}, ...},
          "date": "2026-11-17", "hour": 17, "minutes": 52, "seconds": 35,
          "source": "cubanomic_live",
        }
        o None si falla (el motivo queda en el log).

    `meta.messages` es la cantidad de ofertas reales detrás de la mediana: 0 significa
    valor fijo de referencia, no una tasa del mercado de las últimas horas.
    """
    token = token or get_settings().cubanomic_token
    if not token:
        logger.warning("Cubanomic live: CUBANOMIC_TOKEN no está configurado")
        return None

    now = datetime.now(timezone.utc)
    params = {
        "msg": "false",
        "date_from": (now - timedelta(hours=hours_back)).strftime("%Y-%m-%d %H:%M:%S"),
        "date_to": now.strftime("%Y-%m-%d %H:%M:%S"),
        "token": token,
    }
    headers = {
        "Accept": "application/json",
        "Referer": REFERER,
        "Origin": "https://iframe.cubanomic.com",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                CUBANOMIC_API_URL, params=params, headers=headers, timeout=timeout
            )
            response.raise_for_status()
            raw = response.json()
        return _normalize_to_eltoque_format(raw)
    except httpx.HTTPStatusError as e:
        logger.warning("Cubanomic live HTTP %s", e.response.status_code)
    except httpx.TimeoutException:
        logger.warning("Cubanomic live: timeout")
    except httpx.RequestError as e:
        logger.warning("Cubanomic live: error de red (%s)", type(e).__name__)
    except ValueError:
        logger.warning("Cubanomic live: la respuesta no es JSON")
    except Exception as e:
        logger.error("Cubanomic live: error inesperado: %s", e)
    return None


def _normalize_to_eltoque_format(raw: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Convierte la respuesta de Cubanomic al formato que espera el resto del sistema."""
    stats = raw.get("statistics") if isinstance(raw, dict) else None
    if not stats:
        logger.warning("Cubanomic live: respuesta sin 'statistics'")
        return None

    tasas: dict[str, float] = {}
    meta: dict[str, dict[str, Any]] = {}

    for key, info in stats.items():
        if not isinstance(info, dict):
            continue
        code = str(key).upper()
        code = CURRENCY_MAP.get(code, code)
        if code in EXCLUDED:
            continue
        try:
            rate = float(info.get("median"))
        except (TypeError, ValueError):
            continue
        if rate <= 0:
            continue

        messages = int(info.get("count_messages") or 0)
        # Si dos claves colapsan en la misma moneda (ECU y EUR), gana la mejor respaldada
        if code in meta and messages <= meta[code]["messages"]:
            continue
        tasas[code] = rate
        meta[code] = {"messages": messages, "median_diff": info.get("median_diff")}

    if not tasas:
        logger.warning("Cubanomic live: ninguna moneda utilizable en la respuesta")
        return None

    return {
        "tasas": tasas,
        "meta": meta,
        "date": raw.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "hour": raw.get("hour", 0),
        "minutes": raw.get("minutes", 0),
        "seconds": raw.get("seconds", 0),
        "source": "cubanomic_live",
    }
