"""Modelos para estadísticas del bot de Telegram."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, func

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

    def __repr__(self) -> str:
        return f"<BotUser(user_id={self.user_id}, username={self.username})>"


class BotCommandStat(Base):
    """Registro de uso de comandos del bot de Telegram."""

    __tablename__ = "bot_command_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    command = Column(String(50), nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    source = Column(String(50), nullable=True)  # Fuente consultada si aplica (eltoque, bcc, cadeca)
    success = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    def __repr__(self) -> str:
        return f"<BotCommandStat(command={self.command}, user_id={self.user_id})>"
