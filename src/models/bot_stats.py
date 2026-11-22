"""Modelos para estadísticas del bot de Telegram."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, Float, func
from sqlalchemy import true as sa_true, false as sa_false

from src.database import Base


class BotUser(Base):
    """Registro de usuarios del bot de Telegram."""

    __tablename__ = "bot_users"

    user_id = Column(BigInteger, primary_key=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    first_seen = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    total_commands = Column(Integer, nullable=False, default=0)
    # False = el usuario bloqueo el bot (taso-bot#72 F2). /ms no le escribe y la purga lo borra tras N dias.
    is_reachable = Column(Boolean, nullable=False, default=True, server_default=sa_true())
    unreachable_since = Column(DateTime(timezone=True), nullable=True)
    # True = /silencio: no recibe difusiones masivas de /ms (taso-bot#72 F5). Alertas y suscripciones siguen.
    is_muted = Column(Boolean, nullable=False, default=False, server_default=sa_false())

    def __repr__(self) -> str:
        return f"<BotUser(user_id={self.user_id}, username={self.username})>"


class BotCommandStat(Base):
    """Registro de uso de comandos del bot de Telegram."""

    __tablename__ = "bot_command_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    command = Column(String(50), nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    source = Column(String(50), nullable=True)  # Fuente consultada si aplica (eltoque, bcc)
    success = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    def __repr__(self) -> str:
        return f"<BotCommandStat(command={self.command}, user_id={self.user_id})>"


class BroadcastLog(Base):
    """Una difusion de /ms (taso-bot#72 F3). Solo contadores: NUNCA el texto del mensaje.

    shortcut: sin purga, una fila por difusion crece muy lento; podar si llegara a miles.
    """

    __tablename__ = "broadcast_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    admin_id = Column(BigInteger, nullable=False)
    kind = Column(String(10), nullable=False)  # text | photo
    segment = Column(String(30), nullable=False, default="todos", server_default="todos")
    recipients = Column(Integer, nullable=False)
    ok = Column(Integer, nullable=False)
    blocked = Column(Integer, nullable=False)
    errors = Column(Integer, nullable=False)
    duration_s = Column(Float, nullable=False)

    def __repr__(self) -> str:
        return f"<BroadcastLog(id={self.id}, admin_id={self.admin_id}, recipients={self.recipients})>"
