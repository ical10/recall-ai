"""add vocab generation fields: interest_tags, milestone markers, source

Revision ID: 0004_add_vocab_generation_fields
Revises: 0003_add_user_timezone
Create Date: 2026-05-16 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_add_vocab_generation_fields"
down_revision: str | None = "0003_add_user_timezone"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


STARTER_TOKENS = (
    "friend",
    "hungry",
    "happy",
    "morning",
    "family",
    "school",
    "play",
    "animal",
    "rain",
    "color",
    "night",
    "story",
)


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "interest_tags",
            sa.JSON(),
            nullable=False,
            server_default='["animals","family","food"]',
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "last_personalized_milestone",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "last_milestone_seen",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "vocab_items",
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default="user",
        ),
    )

    # Backfill source='starter' for the 12 known starter-vocab tokens so the
    # observability column reflects true provenance instead of defaulting
    # them all to 'user'.
    starter_list = ",".join(f"'{t}'" for t in STARTER_TOKENS)
    op.execute(
        f"UPDATE vocab_items SET source = 'starter' "
        f"WHERE language = 'en' AND token IN ({starter_list})"
    )


def downgrade() -> None:
    op.drop_column("vocab_items", "source")
    op.drop_column("users", "last_milestone_seen")
    op.drop_column("users", "last_personalized_milestone")
    op.drop_column("users", "interest_tags")
