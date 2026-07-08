"""Add tickets table for the user→admin support/contact system (/tkt).

Los tickets se crean desde taso-bot (cualquier usuario) y se gestionan por
los admins vía notificación directa + endpoints admin. Los campos de Stars
(stars_invoice_payload, stars_paid) quedan reservados NULL/False para la
Fase 3 (promoción paga), sin usarse todavía.

Ver docs/plans/2026-07-07-comando-tkt-tickets.md

Revisión anterior: 4d_add_alert_note
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4e_add_tickets"
down_revision: Union[str, None] = "4d_add_alert_note"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea la tabla tickets."""
    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("claimed_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stars_invoice_payload", sa.String(length=100), nullable=True),
        sa.Column("stars_paid", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_tickets_user_id", "tickets", ["user_id"])


def downgrade() -> None:
    """Elimina la tabla tickets."""
    op.drop_index("ix_tickets_user_id", table_name="tickets")
    op.drop_table("tickets")
