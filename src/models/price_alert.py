"""PriceAlert model for managing user crypto price alerts."""

from datetime import datetime, timezone
from sqlalchemy import Column, BigInteger, Integer, String, Float, DateTime, func

from src.database import Base


class PriceAlert(Base):
    """Alerta de precio de criptomoneda por usuario."""

    __tablename__ = "price_alerts"

    id = Column(Integer, autoincrement=True, primary_key=True)
    user_id = Column(BigInteger, nullable=False, index=True)   # Telegram user_id
    coin = Column(String(20), nullable=False, index=True)       # "BTC", "ETH", etc.
    target_price = Column(Float, nullable=False)
    condition = Column(String(10), nullable=False)              # "ABOVE" | "BELOW"
    status = Column(String(10), nullable=False, default="ACTIVE")  # "ACTIVE" | "TRIGGERED"
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    triggered_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<PriceAlert(id={self.id}, user_id={self.user_id}, "
            f"coin={self.coin}, {self.condition} {self.target_price}, status={self.status})>"
        )
