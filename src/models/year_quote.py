"""YearQuote model for storing daily quotes/phrases for the year module."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, func

from src.database import Base


class YearQuote(Base):
    __tablename__ = "year_quote"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quote_text = Column(String(1000), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<YearQuote(id={self.id}, text={self.quote_text!r})>"
