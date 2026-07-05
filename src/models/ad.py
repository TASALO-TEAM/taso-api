"""Ad model for the centralized announcements/ads system.

Los anuncios se gestionan desde taso-bot (comando /ads, solo admins) y se sirven
a cualquier consumidor (taso-bot, taso-app, taso-ext) vía endpoints públicos de
solo lectura. Ver docs/plans/2026-07-04-sistema-anuncios.md para el diseño completo.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, BigInteger, DateTime, func

from src.database import Base


class Ad(Base):
    """Anuncio del sistema centralizado de ads."""

    __tablename__ = "ads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    text = Column(String(300), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    is_sponsored = Column(Boolean, nullable=False, default=False, server_default="false")
    weight = Column(Integer, nullable=False, default=1, server_default="1")
    created_by = Column(BigInteger, nullable=True)  # Telegram user_id del admin
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    def __repr__(self) -> str:
        return (
            f"<Ad(id={self.id}, active={self.is_active}, "
            f"sponsored={self.is_sponsored}, weight={self.weight})>"
        )
