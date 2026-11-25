"""Cubos de liquidaciones de futuros (taso-bot M3a)."""

from sqlalchemy import Column, DateTime, Float, Integer, String, UniqueConstraint

from src.database import Base


class LiquidationBucket(Base):
    """Liquidaciones acumuladas por minuto, exchange, simbolo y lado.

    side = lado de la POSICION liquidada (long | short). notional_usd ya esta en USD.
    Se purga a las 25 h: solo sirve para ventanas de hasta 24 h.
    """

    __tablename__ = "liquidation_buckets"
    __table_args__ = (UniqueConstraint("bucket", "exchange", "symbol", "side", name="uq_liq_bucket_key"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    bucket = Column(DateTime(timezone=True), nullable=False, index=True)
    exchange = Column(String(10), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(5), nullable=False)
    notional_usd = Column(Float, nullable=False, default=0.0)
    n = Column(Integer, nullable=False, default=0)
