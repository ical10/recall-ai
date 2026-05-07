"""initial: users, vocab_items, reviews

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-05 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("google_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("avatar_url", sa.String(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("google_id", name=op.f("uq_users_google_id")),
    )

    op.create_table(
        "vocab_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("token", sa.String(255), nullable=False),
        sa.Column("language", sa.String(35), nullable=False),
        sa.Column("part_of_speech", sa.String(32), nullable=True),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("example_sentence", sa.Text(), nullable=True),
        sa.Column("audio_url", sa.String(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("token", "language", name="uq_vocab_items_token_language"),
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("vocab_item_id", sa.Uuid(), nullable=False),
        sa.Column("ease_factor", sa.Float(), server_default="2.5", nullable=False),
        sa.Column("interval_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("repetitions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_reviews_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["vocab_item_id"],
            ["vocab_items.id"],
            name=op.f("fk_reviews_vocab_item_id_vocab_items"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "vocab_item_id", name="uq_reviews_user_id_vocab_item_id"),
    )
    op.create_index(op.f("ix_reviews_user_id"), "reviews", ["user_id"], unique=False)
    op.create_index(op.f("ix_reviews_vocab_item_id"), "reviews", ["vocab_item_id"], unique=False)
    op.create_index(op.f("ix_reviews_due_at"), "reviews", ["due_at"], unique=False)


def downgrade() -> None:
    op.drop_table("reviews")
    op.drop_table("vocab_items")
    op.drop_table("users")
