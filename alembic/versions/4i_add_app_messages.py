"""Add app_messages table (mensajes del equipo para la sección Alertas de la app Android).

Se publican desde taso-bot (/msapp, solo admins) y se sirven con un endpoint público de
solo lectura. Migración puramente ADITIVA: no modifica ninguna tabla existente.

Seguridad: la tabla nace con Row Level Security activo y sin políticas, igual que las
otras 17 tablas del esquema public (ver el fix de `rls_disabled_in_public` en Supabase).
Solo taso-api, que conecta como `postgres` (dueño de la tabla), puede leerla o escribirla;
la Data API de Supabase (roles anon/authenticated) queda bloqueada. En SQLite (desarrollo)
no existe RLS y ese paso se omite.

Revisión anterior: 4h_add_rate_snapshot_index
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4i_add_app_messages"
down_revision: Union[str, None] = "4h_add_rate_snapshot_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea la tabla app_messages (con RLS activo en PostgreSQL)."""
    op.create_table(
        "app_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("format", sa.String(length=16), server_default="telegram", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE app_messages ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    """Elimina la tabla app_messages."""
    op.drop_table("app_messages")
