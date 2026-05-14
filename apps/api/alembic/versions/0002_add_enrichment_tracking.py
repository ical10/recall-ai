"""add enrichment tracking columns to vocab_items

Revision ID: 0002_add_enrichment_tracking
Revises: 0001_initial
Create Date: 2026-05-14 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_enrichment_tracking"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vocab_items",
        sa.Column("enrichment_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "vocab_items",
        sa.Column("last_enrichment_attempted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("vocab_items", "last_enrichment_attempted_at")
    op.drop_column("vocab_items", "enrichment_attempts")
