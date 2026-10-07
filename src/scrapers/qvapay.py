"""Scraper de la API pública P2P de QvaPay (promedios de compra/venta por método de pago)."""

import asyncio
import logging
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)

QVAPAY_URL = "https://api.qvapay.com/p2p/completed_pairs_average"
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
}


def _to_float(value) -> Optional[float]:
    """Convierte a float; None si el valor falta, no es numérico o no es positivo."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


async def _fetch_coin(
    client: httpx.AsyncClient, coin_code: str
) -> Optional[Dict[str, Optional[float]]]:
    """Consulta una moneda. Devuelve {"buy": x, "sell": y} o None si no hay datos.

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


async def fetch_qvapay(
    timeout: float = DEFAULT_TIMEOUT,
) -> Optional[Dict[str, Dict[str, Optional[float]]]]:
    """
    Obtiene los promedios P2P de QvaPay para todos los métodos de pago.

    Cada valor es "cuánto de ese método por 1 USD de QvaPay" (no son todos CUP por unidad).
    Consulta las monedas de QVAPAY_COINS en paralelo y omite las que no tienen datos
    (p. ej. SBERBANK casi siempre).

    Returns:
        {etiqueta: {"buy": average_buy | None, "sell": average_sell | None}}, o None si
        no respondió ninguna moneda.
    """
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=4.0)
        ) as client:
            results = await asyncio.gather(
                *(_fetch_coin(client, code) for code in QVAPAY_COINS.values())
            )
    except Exception as e:
        logger.warning("QvaPay: error inesperado: %s", e)
        return None

    rates = {
        label: value
        for label, value in zip(QVAPAY_COINS.keys(), results)
        if value is not None
    }
    return rates or None
