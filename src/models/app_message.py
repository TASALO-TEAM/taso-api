"""AppMessage model: mensajes del equipo TASALO que se muestran dentro de la app Android.

Se publican desde taso-bot (comando /msapp, solo admins) y la app los consulta con un
endpoint público de solo lectura (GET /api/v1/app/messages), igual que el sistema de
anuncios (`Ad`). Se guardan todos; el endpoint devuelve solo los últimos N, así quien
abre la app después de que se enviaron un mensaje también lo ve.

Ver docs/plans/2026-10-01-app-mensajes-notificaciones-y-blog.md (shared, en tasalo/docs/plans).
"""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String, Text, func

from src.database import Base


class AppMessage(Base):
    """Mensaje para la sección Alertas de la app Android."""

    __tablename__ = "app_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Primera línea del mensaje: es lo que se ve con el mensaje contraído.
    title = Column(String(120), nullable=False)
    # Cuerpo en Markdown (hasta 4096 caracteres, igual que un mensaje de Telegram).
    body = Column(Text, nullable=False)
    # "telegram" = Markdown legacy de Telegram (*negrita*, _cursiva_); "markdown" = estándar.
    format = Column(String(16), nullable=False, default="telegram", server_default="telegram")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by = Column(BigInteger, nullable=True)  # Telegram user_id del admin
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<AppMessage(id={self.id}, active={self.is_active}, format={self.format})>"
