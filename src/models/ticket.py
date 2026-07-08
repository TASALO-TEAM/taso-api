"""Ticket model for the user→admin support/contact system.

Los tickets se crean desde taso-bot (comando /tkt, cualquier usuario) y se
gestionan por los admins vía notificación directa en Telegram + endpoints
admin. Ver docs/plans/2026-07-07-comando-tkt-tickets.md para el diseño
completo.

Campos stars_invoice_payload / stars_paid reservados para la Fase 3
(promoción paga con Telegram Stars) — NULL/False hasta que esa fase se
implemente, para no tener que migrar la tabla de nuevo.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, func

from src.database import Base


class Ticket(Base):
    """Ticket de soporte/contacto abierto por un usuario hacia los admins."""

    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    kind = Column(String(20), nullable=False)  # "bug" | "promo"
    message = Column(String(1000), nullable=False)
    status = Column(String(20), nullable=False, default="open", server_default="open")
    # "open" | "in_progress" | "resolved" | "closed"
    claimed_by = Column(BigInteger, nullable=True)  # admin_id que lo tomó
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    # Reservado para Fase 3 (pagos con Telegram Stars) — no usar todavía.
    stars_invoice_payload = Column(String(100), nullable=True)
    stars_paid = Column(Boolean, nullable=False, default=False, server_default="false")

    def __repr__(self) -> str:
        return f"<Ticket(id={self.id}, kind={self.kind}, status={self.status}, user_id={self.user_id})>"
