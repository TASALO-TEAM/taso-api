"""Elimina CADECA: columnas cadeca_* de history_snapshots y filas de esa fuente.

Se purgan las filas con source='cadeca' de rate_snapshots e image_snapshots.
bot_command_stats NO se toca (conserva las estadisticas historicas de comandos).
El downgrade solo recrea las columnas (vacias): los datos borrados no se recuperan,
para eso esta /db backup antes de aplicar.

Revision anterior: 4i_add_app_messages
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4j_drop_cadeca"
down_revision: Union[str, None] = "4i_add_app_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLS = ("cadeca_usd", "cadeca_eur", "cadeca_mlc")


def upgrade() -> None:
    op.execute("DELETE FROM rate_snapshots WHERE source = 'cadeca'")
    op.execute("DELETE FROM image_snapshots WHERE source = 'cadeca'")
    with op.batch_alter_table("history_snapshots") as batch:
        for col in COLS:
            batch.drop_column(col)


def downgrade() -> None:
    with op.batch_alter_table("history_snapshots") as batch:
        for col in COLS:
            batch.add_column(sa.Column(col, sa.Float(), nullable=True))
