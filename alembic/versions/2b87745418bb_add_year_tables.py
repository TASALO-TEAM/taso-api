"""Add year tables: year_quote, year_subscription, year_extra_flag

Revision ID: 2b87745418bb
Revises: a6863f7aec9a
Create Date: 2026-05-16
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b87745418bb'
down_revision: Union[str, Sequence[str], None] = 'a6863f7aec9a'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        'year_quote',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('quote_text', sa.String(length=1000), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('year_quote', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_year_quote_created_at'), ['created_at'], unique=False)

    op.create_table(
        'year_subscription',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('hour', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('year_subscription', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_year_subscription_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_year_subscription_created_at'), ['created_at'], unique=False)
        batch_op.create_unique_constraint('uq_year_subscription_user_id', ['user_id'])

    op.create_table(
        'year_extra_flag',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('asked', sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('year', name='uq_year_extra_flag_year')
    )


def downgrade() -> None:
    with op.batch_alter_table('year_subscription', schema=None) as batch_op:
        batch_op.drop_constraint('uq_year_subscription_user_id', type_='unique')
        batch_op.drop_index(batch_op.f('ix_year_subscription_created_at'))
        batch_op.drop_index(batch_op.f('ix_year_subscription_user_id'))

    with op.batch_alter_table('year_quote', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_year_quote_created_at'))

    op.drop_table('year_subscription')
    op.drop_table('year_quote')
    op.drop_table('year_extra_flag')
