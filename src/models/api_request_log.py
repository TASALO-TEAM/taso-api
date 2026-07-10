"""Modelo de log de requests HTTP a la API pública de TASALO.

Registra *todas* las requests que pasan por el middleware de tracking
(ver src/main.py, track_requests), no solo las que taso-bot reporta
manualmente vía /admin/stats/track. Permite tener visibilidad real
sobre el uso de taso-app, taso-ext y taso-extmf, que consumen los
endpoints públicos sin pasar por el bot.

Ver docs/plans/2026-07-08-status-command-v2.md (Fase 1).
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime

from src.database import Base


class ApiRequestLog(Base):
    """Registro de una request HTTP individual a la API."""

    __tablename__ = "api_request_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    method = Column(String(10), nullable=False)
    path = Column(String(200), nullable=False, index=True)
    status_code = Column(Integer, nullable=False)
    duration_ms = Column(Integer, nullable=False)
    # bot | app | ext | extmf | web | unknown (ver _guess_client en main.py)
    client_id = Column(String(20), nullable=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<ApiRequestLog({self.method} {self.path} "
            f"{self.status_code} {self.duration_ms}ms client={self.client_id})>"
        )
