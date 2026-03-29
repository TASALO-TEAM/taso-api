"""ImageSnapshot model for storing captured images."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from src.database import Base


class ImageSnapshot(Base):
    """Snapshot de imágenes capturadas de fuentes web."""

    __tablename__ = "image_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False, index=True)  # "eltoque", "cadeca", etc.
    image_path = Column(String(500), nullable=False)  # Path en filesystem
    thumbnail_path = Column(String(500), nullable=True)  # Thumbnail opcional
    file_size = Column(Integer, nullable=True)  # Tamaño en bytes
    captured_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )
    metadata = Column(JSONB, nullable=True)  # {width, height, url, etc.}

    def __repr__(self) -> str:
        return f"<ImageSnapshot(source={self.source}, id={self.id}, captured_at={self.captured_at})>"
