"""TsplDigest model: último digest /tspl listo para publicar (una sola fila, id=1).

taso-bot lo genera una vez al día (Groq, 11:00 UTC) y lo empuja aquí con
PUT /api/v1/tspl/digest/latest. taso-gcg lo lee con GET para publicarlo en @tasalospl
y en Hive. Guardarlo aquí (y no solo en la caché en memoria de taso-bot) hace que
sobreviva a reinicios y que nadie tenga que volver a llamar a la IA.

Una sola fila a propósito: solo interesa el último; cada PUT la reemplaza.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, Text, func

from src.database import Base

DIGEST_ROW_ID = 1


class TsplDigest(Base):
    """Último digest generado por taso-bot (texto de Telegram + markdown del blog)."""

    __tablename__ = "tspl_digest"

    id = Column(Integer, primary_key=True, autoincrement=False, default=DIGEST_ROW_ID)
    telegram_text = Column(Text, nullable=False)
    blog_markdown = Column(Text, nullable=True)
    # Cuándo lo generó taso-bot (lo manda él): permite a quien lo lee descartar uno viejo.
    generated_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<TsplDigest(generated_at={self.generated_at})>"
