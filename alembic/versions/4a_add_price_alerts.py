"""Add price_alerts table for crypto price alert system.

Agrega la tabla price_alerts que almacena las alertas de precio
de criptomonedas configuradas por usuarios desde taso-bot (/alert).

Revisión anterior: 3a_fix_all_tables
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4a_add_price_alerts"
down_revision: Union[str, None] = "3a_fix_all_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea la tabla price_alerts con sus índices."""
    op.create_table(
        "price_alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("coin", sa.String(length=20), nullable=False),
        sa.Column("target_price", sa.Float(), nullable=False),
        sa.Column("condition", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="ACTIVE"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("price_alerts", schema=None) as batch_op:
        batch_op.create_index("ix_price_alerts_user_id", ["user_id"], unique=False)
        batch_op.create_index("ix_price_alerts_status", ["status"], unique=False)
        batch_op.create_index("ix_price_alerts_coin_status", ["coin", "status"], unique=False)


def downgrade() -> None:
    """Elimina la tabla price_alerts y sus índices."""
    with op.batch_alter_table("price_alerts", schema=None) as batch_op:
        batch_op.drop_index("ix_price_alerts_coin_status")
        batch_op.drop_index("ix_price_alerts_status")
        batch_op.drop_index("ix_price_alerts_user_id")

    op.drop_table("price_alerts")
