"""Avisos de arranque/apagado/errores al grupo de soporte por Telegram.

taso-api no es un bot de Telegram (es FastAPI puro), así que a diferencia
de taso-gcg/taso-bot no puede usar python-telegram-bot para esto. En vez de
traer esa dependencia solo para mandar avisos, se hace un POST directo al
endpoint sendMessage de la Bot API con httpx — mismo LOG_CHAT_ID (grupo)
que ya usan taso-gcg y taso-bot, reutilizando el bot de taso-gcg
(LOG_BOT_TOKEN) porque ya es admin de ese grupo.

Si LOG_CHAT_ID o LOG_BOT_TOKEN no están configurados, notify() no hace
nada — el resto de la app sigue funcionando exactamente igual.
"""

from __future__ import annotations

import logging

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)

_TELEGRAM_API_BASE = "https://api.telegram.org"
_TIMEOUT_SECONDS = 5.0
async def notify(mensaje: str) -> None:
    """Manda `mensaje` al grupo de soporte (LOG_CHAT_ID). Best-effort: nunca
    lanza — si falla, solo queda un log.debug (el error real ya se logueó
    donde se llamó a notify())."""
    settings = get_settings()
    if not settings.log_chat_id or not settings.log_bot_token:
        return

    url = f"{_TELEGRAM_API_BASE}/bot{settings.log_bot_token}/sendMessage"
    payload = {"chat_id": settings.log_chat_id, "text": mensaje}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.debug(
                    "⚠️ No se pudo notificar a LOG_CHAT_ID (HTTP %s): %s",
                    resp.status_code, resp.text[:200],
                )
    except Exception as e:
        logger.debug("⚠️ No se pudo notificar a LOG_CHAT_ID: %s", e)
