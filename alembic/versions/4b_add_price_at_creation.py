"""Add price_at_creation column to price_alerts.

Agrega la columna price_at_creation a la tabla price_alerts para almacenar
el precio real de la moneda en el momento en que el usuario creó la alerta.

Esto permite al checker detectar cruces reales del nivel objetivo y evitar
falsos positivos (alertas que se disparaban de inmediato porque el precio ya
estaba por encima o por debajo del target al momento de la creación).

Lógica de cruce:
  ABOVE: dispara cuando current_price >= target Y price_at_creation < target
  BELOW: dispara cuando current_price <= target Y price_at_creation > target

Revisión anterior: 4a_add_price_alerts
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4b_add_price_at_creation"
down_revision: Union[str, None] = "4a_add_price_alerts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Añade la columna price_at_creation a price_alerts (nullable para compatibilidad)."""
    with op.batch_alter_table("price_alerts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("price_at_creation", sa.Float(), nullable=True)
        )


def downgrade() -> None:
    """Elimina la columna price_at_creation de price_alerts."""
    with op.batch_alter_table("price_alerts", schema=None) as batch_op:
        batch_op.drop_column("price_at_creation")
