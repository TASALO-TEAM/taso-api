"""Agrega bot_users.is_reachable y unreachable_since (taso-bot#72, Fase 2).

Migracion ADITIVA: is_reachable es BOOLEAN NOT NULL con default true (todos los
usuarios existentes quedan alcanzables) y unreachable_since es nullable.

Revision anterior: 4k_add_rate_snapshot_offers
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4l_add_bot_users_reachability"
down_revision: Union[str, None] = "4k_add_rate_snapshot_offers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bot_users",
        sa.Column("is_reachable", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "bot_users",
        sa.Column("unreachable_since", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    with op.batch_alter_table("bot_users") as batch:
        batch.drop_column("unreachable_since")
        batch.drop_column("is_reachable")
