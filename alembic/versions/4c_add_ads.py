"""Add ads table for centralized announcements system.

Sistema de anuncios centralizado (comando /ads en taso-bot, solo admins).
Ver docs/plans/2026-07-04-sistema-anuncios.md para el diseño completo.

- is_active: permite pausar un anuncio sin borrarlo.
- is_sponsored: distingue "Patrocinado" (tercero/pago) de "Aviso" (propio) en el
  bloque que se inyecta en los mensajes del bot.
- weight: frecuencia relativa al elegir un anuncio al azar (default 1 = igual peso).

Revisión anterior: 4b_add_price_at_creation
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4c_add_ads"
down_revision: Union[str, None] = "4b_add_price_at_creation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea la tabla ads."""
    op.create_table(
        "ads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("text", sa.String(length=300), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_sponsored", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("weight", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Elimina la tabla ads."""
    op.drop_table("ads")
