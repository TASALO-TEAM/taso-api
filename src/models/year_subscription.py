"""YearSubscription model for daily year-progress alert subscriptions."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, BigInteger, DateTime, func

from src.database import Base


class YearSubscription(Base):
    __tablename__ = "year_subscription"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True, unique=True)
    hour = Column(Integer, nullable=False)  # UTC hour (0-23)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<YearSubscription(user_id={self.user_id}, hour={self.hour})>"
