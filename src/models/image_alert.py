"""UserImageAlert model for managing user image alert preferences."""

from datetime import datetime, timezone
from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, func

from src.database import Base


class UserImageAlert(Base):
    """Configuración de alertas de imágenes por usuario."""

    __tablename__ = "user_image_alerts"

    user_id = Column(BigInteger, primary_key=True)  # Telegram user_id
    alert_time = Column(String(5), nullable=False, default="07:15")  # Formato "HH:MM"
    format_type = Column(String(20), nullable=False, default="photo")  # "photo" | "document"
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<UserImageAlert(user_id={self.user_id}, alert_time={self.alert_time}, enabled={self.enabled})>"
