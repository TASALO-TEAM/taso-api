"""Agrega rate_snapshots.offers (ofertas reales detras de una tasa de ElToque via Cubanomic).

Migracion ADITIVA: una columna INTEGER nullable, sin default y sin reescribir filas.
NULL = tasa de la API oficial de ElToque o de otra fuente (se trata como mercado).

Revision anterior: 4j_drop_cadeca
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4k_add_rate_snapshot_offers"
down_revision: Union[str, None] = "4j_drop_cadeca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("rate_snapshots", sa.Column("offers", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("rate_snapshots") as batch:
        batch.drop_column("offers")
