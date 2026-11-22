"""Crea la tabla broadcast_log (taso-bot#72, Fase 3).

Migracion ADITIVA: tabla nueva, no modifica ninguna existente. Guarda solo los
contadores de cada difusion de /ms; nunca el texto del mensaje.

Revision anterior: 4l_add_bot_users_reachability
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4m_add_broadcast_log"
down_revision: Union[str, None] = "4l_add_bot_users_reachability"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "broadcast_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("admin_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("segment", sa.String(30), nullable=False, server_default="todos"),
        sa.Column("recipients", sa.Integer(), nullable=False),
        sa.Column("ok", sa.Integer(), nullable=False),
        sa.Column("blocked", sa.Integer(), nullable=False),
        sa.Column("errors", sa.Integer(), nullable=False),
        sa.Column("duration_s", sa.Float(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("broadcast_log")
