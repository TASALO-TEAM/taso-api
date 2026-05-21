"""Consolidated: all missing tables in one migration.

Covers the gap from the initial migration head `a980a08ecd3a` through
all intermediate tables that were absent in production:
  a980a08ecd3a  → rate_snapshots, scheduler_status  (was a980)
  b123456789ab  → bot_users, bot_command_stats      (was b123)
  a77989368d5e  → cubanomic_rates                    (was a779)
  b47e6acb1437  → history_snapshots                  (was b47e6)
  a6863f7aec9a  → image_snapshots, user_image_alerts (was a6863)

Year tables (year_quote, year_subscription, year_extra_flag) already
exist in production and are NOT recreated here.
Back‑reference ──`scheduler_status` index.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3a_fix_all_tables"
down_revision: Union[str, None] = "a980a08ecd3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create every table that was missing from production in one shot.

    Tables rate_snapshots and scheduler_status are handled by down_revision
    a980a08ecd3a (initial migration).  This revision covers what was absent:
      b123456789ab  → bot_users, bot_command_stats            (was b123)
      a77989368d5e  → cubanomic_rates                         (was a779)
      b47e6acb1437  → history_snapshots                       (was b47e6)
      a6863f7aec9a  → image_snapshots, user_image_alerts      (was a6863)
    """
    # ── b123456789ab ──────────────────────────────────────────────────
    op.create_table(
        "bot_users",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=True),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_commands", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "bot_command_stats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("command", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("bot_command_stats", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_bot_command_stats_command"), ["command"], unique=False)
        batch_op.create_index(batch_op.f("ix_bot_command_stats_user_id"), ["user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_bot_command_stats_created_at"), ["created_at"], unique=False)

    # ── a77989368d5e ──────────────────────────────────────────────────
    op.create_table(
        "cubanomic_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usd_rate", sa.Float(), nullable=False),
        sa.Column("eur_rate", sa.Float(), nullable=False),
        sa.Column("mlc_rate", sa.Float(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("cubanomic_rates", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_cubanomic_rates_id"), ["id"], unique=False)
        batch_op.create_index("ix_cubanomic_fetched_at", ["fetched_at"], unique=False)

    # ── b47e6acb1437 ──────────────────────────────────────────────────
    op.create_table(
        "history_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("eltoque_usd", sa.Float(), nullable=True),
        sa.Column("eltoque_eur", sa.Float(), nullable=True),
        sa.Column("eltoque_mlc", sa.Float(), nullable=True),
        sa.Column("cadeca_usd", sa.Float(), nullable=True),
        sa.Column("cadeca_eur", sa.Float(), nullable=True),
        sa.Column("cadeca_mlc", sa.Float(), nullable=True),
        sa.Column("bcc_usd", sa.Float(), nullable=True),
        sa.Column("bcc_eur", sa.Float(), nullable=True),
        sa.Column("bcc_mlc", sa.Float(), nullable=True),
        sa.Column("binance_btc", sa.Float(), nullable=True),
        sa.Column("binance_eth", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── a6863f7aec9a ──────────────────────────────────────────────────
    op.create_table(
        "image_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("image_path", sa.String(length=500), nullable=False),
        sa.Column("thumbnail_path", sa.String(length=500), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("image_snapshots", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_image_snapshots_captured_at"), ["captured_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_image_snapshots_source"), ["source"], unique=False)

    op.create_table(
        "user_image_alerts",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("alert_time", sa.String(length=5), nullable=False),
        sa.Column("format_type", sa.String(length=20), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    """Drop every table created by upgrade(), in reverse order."""
    with op.batch_alter_table("image_snapshots", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_image_snapshots_source"))
        batch_op.drop_index(batch_op.f("ix_image_snapshots_captured_at"))

    op.drop_table("user_image_alerts")
    op.drop_table("image_snapshots")
    op.drop_table("history_snapshots")

    with op.batch_alter_table("cubanomic_rates", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_cubanomic_rates_fetched_at"))
        batch_op.drop_index(batch_op.f("ix_cubanomic_rates_id"))

    with op.batch_alter_table("bot_command_stats", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_bot_command_stats_created_at"))
        batch_op.drop_index(batch_op.f("ix_bot_command_stats_user_id"))
        batch_op.drop_index(batch_op.f("ix_bot_command_stats_command"))

    op.drop_table("cubanomic_rates")
    op.drop_table("bot_command_stats")
    op.drop_table("bot_users")
