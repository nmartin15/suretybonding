"""add signing keys table

Revision ID: 20260311_0002
Revises: 20260311_0001
Create Date: 2026-03-11 18:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260311_0002"
down_revision = "20260311_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signing_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key_id", sa.String(length=128), nullable=False),
        sa.Column("private_key_pem", sa.Text(), nullable=False),
        sa.Column("certificate_pem", sa.Text(), nullable=False),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=False),
        sa.Column("not_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_signing_keys_is_active"), "signing_keys", ["is_active"], unique=False
    )
    op.create_index(
        op.f("ix_signing_keys_key_id"), "signing_keys", ["key_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_signing_keys_key_id"), table_name="signing_keys")
    op.drop_index(op.f("ix_signing_keys_is_active"), table_name="signing_keys")
    op.drop_table("signing_keys")
