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


class HistorySnapshot(Base):
    """
    Historical snapshot of all rates from the 5-minute refresh cycle.
    Automatically populated by the existing scheduler job.
    """

    __tablename__ = "history_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    fetched_at = Column(DateTime(timezone=True), index=True, nullable=False)

    # ElToque rates
    eltoque_usd = Column(Float)
    eltoque_eur = Column(Float)
    eltoque_mlc = Column(Float)

    # CADECA rates (average of buy/sell)
    cadeca_usd = Column(Float)
    cadeca_eur = Column(Float)
    cadeca_mlc = Column(Float)

    # BCC rates (average of buy/sell)
    bcc_usd = Column(Float)
    bcc_eur = Column(Float)
    bcc_mlc = Column(Float)

    # Binance rates (crypto, stored separately)
    binance_btc = Column(Float)
    binance_eth = Column(Float)

    def __repr__(self) -> str:
        return f"<HistorySnapshot(fetched_at={self.fetched_at}, eltoque_usd={self.eltoque_usd}, cadeca_usd={self.cadeca_usd}, bcc_usd={self.bcc_usd})>"
