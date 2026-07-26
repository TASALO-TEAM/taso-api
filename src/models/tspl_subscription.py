"""TsplSubscription model — hasta 2 horarios diarios de envío de /tspl.

Ver docs/plans/2026-07-24-tspl-suscripcion-horarios.md
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, BigInteger, DateTime, UniqueConstraint, func

from src.database import Base


class TsplSubscription(Base):
    __tablename__ = "tspl_subscription"
    __table_args__ = (
        UniqueConstraint("user_id", "hour", name="uq_tspl_subscription_user_hour"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)  # NO unique solo — permite hasta 2 filas
    hour = Column(Integer, nullable=False)  # UTC hour (0-23)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<TsplSubscription(user_id={self.user_id}, hour={self.hour})>"
