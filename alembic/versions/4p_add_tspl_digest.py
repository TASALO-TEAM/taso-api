"""Add tspl_digest table (último digest /tspl listo para publicar, una sola fila).

taso-bot lo empuja una vez al día y taso-gcg lo lee para publicarlo en @tasalospl y Hive.
Migración puramente ADITIVA. Nace con RLS activo y sin políticas, igual que el resto de
tablas del esquema public (solo taso-api, que conecta como `postgres`, puede usarla).

Revisión anterior: 4n_add_bot_users_is_muted

NOTA DE FUSIÓN: la rama feat/liquidaciones-m3-b añade 4o_add_liquidation_buckets también
sobre 4o (liquidaciones)
(si no, Alembic verá dos cabezas).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4p_add_tspl_digest"
down_revision: Union[str, None] = "4o_add_liquidation_buckets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea la tabla tspl_digest (con RLS activo en PostgreSQL)."""
    op.create_table(
        "tspl_digest",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("telegram_text", sa.Text(), nullable=False),
        sa.Column("blog_markdown", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE tspl_digest ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    """Elimina la tabla tspl_digest."""
    op.drop_table("tspl_digest")
