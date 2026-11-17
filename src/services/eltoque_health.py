"""Salud de la fuente ElToque: avisos al grupo de soporte.

Estados (por ciclo de refresh):
  ok        la API oficial respondió.
  degraded  la API falló, pero Cubanomic respondió (las tasas siguen llegando).
  down      fallaron las dos: se quedan las últimas tasas guardadas.

Solo se avisa en cambios de estado y, mientras siga mal, un recordatorio cada
REMINDER_SECONDS. Además se avisa con anticipación del vencimiento del token.
El estado vive en memoria: tras un reinicio, un estado no-ok vuelve a avisar (deseado).
"""

from __future__ import annotations

import base64
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from src.config import get_settings
from src.services.alert_notifier import notify

logger = logging.getLogger(__name__)

REMINDER_SECONDS = 6 * 3600
TOKEN_WARN_DAYS = (14, 7, 3, 1)

_mode: Optional[str] = None
_last_alert_at: float = 0.0
_warned_days: set[int] = set()


def reset_state() -> None:
    """Reinicia el estado en memoria (uso en tests)."""
    global _mode, _last_alert_at
    _mode, _last_alert_at = None, 0.0
    _warned_days.clear()


def token_days_left(api_key: str) -> Optional[int]:
    """Días hasta que expira el JWT (negativo si ya venció). None si no se puede leer.

    Solo decodifica el payload para leer `exp`; no valida la firma.
    """
    try:
        payload = api_key.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        exp = json.loads(base64.urlsafe_b64decode(payload))["exp"]
        delta = datetime.fromtimestamp(float(exp), timezone.utc) - datetime.now(timezone.utc)
        return delta.days
    except Exception:
        return None


async def report(mode: str, api_reason: Optional[str], extras: int = 0) -> None:
    """Registra el estado del ciclo y avisa al grupo si corresponde.

    Nunca lanza: un fallo aquí no debe romper el ciclo de tasas.
    """
    global _mode, _last_alert_at
    try:
        now = time.monotonic()
        previous = _mode
        _mode = mode

        if mode == "ok":
            if previous in ("degraded", "down"):
                _last_alert_at = 0.0
                await notify("✅ ElToque API recuperada: las tasas vuelven a salir de la fuente oficial.")
            await _check_token_expiry()
            return

        changed = mode != previous
        reminder_due = (now - _last_alert_at) >= REMINDER_SECONDS
        if not (changed or reminder_due):
            return

        _last_alert_at = now
        reason = api_reason or "sin detalle"
        if mode == "degraded":
            await notify(
                "⚠️ ElToque API falló: " + reason + "\n"
                "Las tasas se están sacando de Cubanomic (respaldo). "
                "Si es token vencido, pedir uno nuevo en https://tasas-token.eltoque.com/ "
                "y actualizar ELTOQUE_API_KEY en el .env del VPS."
            )
        else:
            await notify(
                "🚨 ElToque API y Cubanomic fallaron (motivo API: " + reason + ").\n"
                "Se siguen sirviendo las últimas tasas guardadas; revisar el VPS y los logs de taso-api."
            )
    except Exception:
        logger.exception("eltoque_health.report falló")


async def _check_token_expiry() -> None:
    """Avisa cuando faltan 14/7/3/1 días para que venza el token (una vez por umbral)."""
    days = token_days_left(get_settings().eltoque_api_key or "")
    if days is None or days < 0:
        return
    t = min((x for x in TOKEN_WARN_DAYS if days <= x), default=None)
    if t is None or t in _warned_days:
        return
    _warned_days.update(x for x in TOKEN_WARN_DAYS if x >= t)
    await notify(
        f"⏳ El token de ElToque vence en {days} día(s). "
        "Pedir uno nuevo en https://tasas-token.eltoque.com/ y actualizar ELTOQUE_API_KEY en el VPS."
    )
