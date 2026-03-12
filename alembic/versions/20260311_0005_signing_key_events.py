"""create signing key events table

Revision ID: 20260311_0005
Revises: 20260311_0004
Create Date: 2026-03-11 19:35:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260311_0005"
down_revision = "20260311_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signing_key_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("old_key_id", sa.String(length=128), nullable=True),
        sa.Column("new_key_id", sa.String(length=128), nullable=True),
        sa.Column(
            "is_emergency",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("approval_token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_signing_key_events_action"),
        "signing_key_events",
        ["action"],
        unique=False,
    )
    op.create_index(
        op.f("ix_signing_key_events_actor_id"),
        "signing_key_events",
        ["actor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_signing_key_events_created_at"),
        "signing_key_events",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_signing_key_events_created_at"), table_name="signing_key_events"
    )
    op.drop_index(
        op.f("ix_signing_key_events_actor_id"), table_name="signing_key_events"
    )
    op.drop_index(op.f("ix_signing_key_events_action"), table_name="signing_key_events")
    op.drop_table("signing_key_events")
