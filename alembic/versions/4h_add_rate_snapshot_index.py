"""Add index on rate_snapshots.fetched_at — faltaba para que la poda de
retención (1 año, ver docs/plans/2026-08-01-comando-db-gestion-retencion-tasas.md)
y las consultas de histórico existentes (get_history, get_latest_rates) no
hagan table scan.

Revisión anterior: 4g_add_tspl_subscriptions
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "4h_add_rate_snapshot_index"
down_revision: Union[str, None] = "4g_add_tspl_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea el índice faltante en rate_snapshots.fetched_at."""
    op.create_index(
        "ix_rate_snapshots_fetched_at", "rate_snapshots", ["fetched_at"]
    )


def downgrade() -> None:
    """Elimina el índice."""
    op.drop_index("ix_rate_snapshots_fetched_at", table_name="rate_snapshots")
