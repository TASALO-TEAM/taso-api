"""RateSnapshot model for storing exchange rate snapshots."""

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Numeric, DateTime, func

from src.database import Base


class RateSnapshot(Base):
    """Snapshot de tasas de cambio de una fuente específica."""
    
    __tablename__ = "rate_snapshots"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(20), nullable=False, index=True)  # 'eltoque', 'cadeca', 'bcc', 'binance'
    currency = Column(String(20), nullable=False, index=True)  # 'USD', 'EUR', 'MLC', etc.
    buy_rate = Column(Numeric(12, 4), nullable=True)  # Tasa de compra (CADECA)
    sell_rate = Column(Numeric(12, 4), nullable=True)  # Tasa de venta / única
    fetched_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    
    def __repr__(self) -> str:
        return f"<RateSnapshot(source={self.source}, currency={self.currency}, rate={self.sell_rate})>"
