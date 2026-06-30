"""add_word_example_audio_urls_replace_single_audio

Revision ID: 59271050c043
Revises: 0005_add_applied_ratings
Create Date: 2026-06-30 04:10:18.026213+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "59271050c043"
down_revision: str | Sequence[str] | None = "0005_add_applied_ratings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vocab_items",
        sa.Column("word_audio_url", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "vocab_items",
        sa.Column("example_audio_url", sa.String(length=1024), nullable=True),
    )
    op.drop_column("vocab_items", "audio_url")


def downgrade() -> None:
    op.add_column(
        "vocab_items",
        sa.Column(
            "audio_url",
            sa.VARCHAR(length=1024),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.drop_column("vocab_items", "example_audio_url")
    op.drop_column("vocab_items", "word_audio_url")
