"""Crea la tabla liquidation_buckets (taso-bot M3a).

Migracion ADITIVA: tabla nueva, no modifica ninguna existente.

Revision anterior: 4n_add_bot_users_is_muted
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4o_add_liquidation_buckets"
down_revision: Union[str, None] = "4n_add_bot_users_is_muted"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "liquidation_buckets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bucket", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exchange", sa.String(10), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("side", sa.String(5), nullable=False),
        sa.Column("notional_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("n", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("bucket", "exchange", "symbol", "side", name="uq_liq_bucket_key"),
    )
    op.create_index("ix_liquidation_buckets_bucket", "liquidation_buckets", ["bucket"])


def downgrade() -> None:
    op.drop_index("ix_liquidation_buckets_bucket", table_name="liquidation_buckets")
    op.drop_table("liquidation_buckets")
