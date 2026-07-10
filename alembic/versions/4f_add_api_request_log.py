"""Add api_request_log table for HTTP request tracking middleware.

Registra todas las requests que pasan por el middleware track_requests
(src/main.py), no solo lo que taso-bot reporta manualmente vía
/admin/stats/track. Da visibilidad sobre taso-app/taso-ext/taso-extmf,
que consumen los endpoints públicos directamente.

Ver docs/plans/2026-07-08-status-command-v2.md (Fase 1).

Revisión anterior: 4e_add_tickets
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4f_add_api_request_log"
down_revision: Union[str, None] = "4e_add_tickets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea la tabla api_request_log."""
    op.create_table(
        "api_request_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("path", sa.String(length=200), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_api_request_log_path", "api_request_log", ["path"])
    op.create_index("ix_api_request_log_client_id", "api_request_log", ["client_id"])
    op.create_index("ix_api_request_log_created_at", "api_request_log", ["created_at"])


def downgrade() -> None:
    """Elimina la tabla api_request_log."""
    op.drop_index("ix_api_request_log_created_at", table_name="api_request_log")
    op.drop_index("ix_api_request_log_client_id", table_name="api_request_log")
    op.drop_index("ix_api_request_log_path", table_name="api_request_log")
    op.drop_table("api_request_log")
