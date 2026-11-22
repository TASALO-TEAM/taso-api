"""Agrega bot_users.is_muted (taso-bot#72, Fase 5: /silencio).

Migracion ADITIVA: BOOLEAN NOT NULL con default false (nadie queda silenciado).

Revision anterior: 4m_add_broadcast_log
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4n_add_bot_users_is_muted"
down_revision: Union[str, None] = "4m_add_broadcast_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bot_users",
        sa.Column("is_muted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    with op.batch_alter_table("bot_users") as batch:
        batch.drop_column("is_muted")
