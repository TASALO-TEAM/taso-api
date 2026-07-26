"""Add tspl_subscription table — hasta 2 horarios diarios de envío de /tspl.

Ver docs/plans/2026-07-24-tspl-suscripcion-horarios.md

Revisión anterior: 4f_add_api_request_log
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4g_add_tspl_subscriptions"
down_revision: Union[str, None] = "4f_add_api_request_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea la tabla tspl_subscription."""
    op.create_table(
        "tspl_subscription",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "hour", name="uq_tspl_subscription_user_hour"),
    )
    op.create_index("ix_tspl_subscription_user_id", "tspl_subscription", ["user_id"])


def downgrade() -> None:
    """Elimina la tabla tspl_subscription."""
    op.drop_index("ix_tspl_subscription_user_id", table_name="tspl_subscription")
    op.drop_table("tspl_subscription")
