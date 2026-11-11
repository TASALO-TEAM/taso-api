"""Modelo HistorySnapshot (historico de tasas del ciclo de refresco)."""

from sqlalchemy import Column, Integer, Float, DateTime

from src.database import Base


class HistorySnapshot(Base):
    """
    Historical snapshot of all rates from the 15-minute refresh cycle.
    Automatically populated by the existing scheduler job.
    """

    __tablename__ = "history_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    fetched_at = Column(DateTime(timezone=True), index=True, nullable=False)

    # ElToque rates
    eltoque_usd = Column(Float)
    eltoque_eur = Column(Float)
    eltoque_mlc = Column(Float)

    # BCC rates (average of buy/sell)
    bcc_usd = Column(Float)
    bcc_eur = Column(Float)
    bcc_mlc = Column(Float)

    # Binance rates (crypto, stored separately)
    binance_btc = Column(Float)
    binance_eth = Column(Float)

    def __repr__(self) -> str:
        return f"<HistorySnapshot(fetched_at={self.fetched_at}, eltoque_usd={self.eltoque_usd}, bcc_usd={self.bcc_usd})>"
