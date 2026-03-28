"""add local history snapshot table

Revision ID: b47e6acb1437
Revises: a77989368d5e
Create Date: 2026-03-28 19:08:27.605598

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b47e6acb1437'
down_revision: Union[str, Sequence[str], None] = 'a77989368d5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'history_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('eltoque_usd', sa.Float(), nullable=True),
        sa.Column('eltoque_eur', sa.Float(), nullable=True),
        sa.Column('eltoque_mlc', sa.Float(), nullable=True),
        sa.Column('cadeca_usd', sa.Float(), nullable=True),
        sa.Column('cadeca_eur', sa.Float(), nullable=True),
        sa.Column('cadeca_mlc', sa.Float(), nullable=True),
        sa.Column('bcc_usd', sa.Float(), nullable=True),
        sa.Column('bcc_eur', sa.Float(), nullable=True),
        sa.Column('bcc_mlc', sa.Float(), nullable=True),
        sa.Column('binance_btc', sa.Float(), nullable=True),
        sa.Column('binance_eth', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('history_snapshots')
