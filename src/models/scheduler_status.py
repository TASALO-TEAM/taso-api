"""SchedulerStatus model for tracking scheduler state."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, func

from src.database import Base


class SchedulerStatus(Base):
    """Estado del scheduler de refrescos."""
    
    __tablename__ = "scheduler_status"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    error_count = Column(Integer, nullable=False, default=0)
    last_error = Column(String, nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    
    def __repr__(self) -> str:
        return f"<SchedulerStatus(last_run={self.last_run_at}, errors={self.error_count})>"
