"""CubanomicRate model for storing daily Cubanomic exchange rates."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, DateTime, Index

from src.database import Base


class CubanomicRate(Base):
    """Cubanomic daily rates snapshot."""

    __tablename__ = "cubanomic_rates"

    id = Column(Integer, primary_key=True, index=True)
    usd_rate = Column(Float, nullable=False)
    eur_rate = Column(Float, nullable=False)
    mlc_rate = Column(Float, nullable=False)
    fetched_at = Column(DateTime(timezone=True), nullable=False, index=True)

    __table_args__ = (
        Index("ix_cubanomic_fetched_at", "fetched_at"),
    )

    def __repr__(self) -> str:
        return f"<CubanomicRate(USD={self.usd_rate}, EUR={self.eur_rate}, MLC={self.mlc_rate}, fetched_at={self.fetched_at})>"
