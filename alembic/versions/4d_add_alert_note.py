"""Add note column to price_alerts for origin tracking.

Permite etiquetar el origen de una alerta cuando se crea desde los botones
de nivel en /graf o /ta (ej. "S1 · Análisis 4h"). Nullable: las alertas
creadas manualmente con /alert siguen funcionando igual, con note=NULL.

Ver docs/plans/2026-07-05-alert-informe-cruce-y-ecosistema.md

Revisión anterior: 4c_add_ads
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4d_add_alert_note"
down_revision: Union[str, None] = "4c_add_ads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Añade la columna note (nullable) a price_alerts."""
    op.add_column(
        "price_alerts",
        sa.Column("note", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    """Elimina la columna note."""
    op.drop_column("price_alerts", "note")
