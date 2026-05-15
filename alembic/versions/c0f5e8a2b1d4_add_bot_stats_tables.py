"""Add bot stats tables (bot_users, bot_command_stats)

Revision ID: c0f5e8a2b1d4
Revises: a6863f7aec9a
Create Date: 2026-05-06 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c0f5e8a2b1d4'
down_revision: Union[str, None] = 'a6863f7aec9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tables bot_users and bot_command_stats already created in b123456789ab.
    # This migration adds the missing foreign key constraint.

    op.create_foreign_key(
        'fk_bot_command_stats_user_id',
        'bot_command_stats', 'bot_users',
        ['user_id'], ['user_id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_bot_command_stats_user_id', 'bot_command_stats', type_='foreignkey')
