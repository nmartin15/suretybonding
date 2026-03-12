"""add signing key revocation reason

Revision ID: 20260311_0004
Revises: 20260311_0003
Create Date: 2026-03-11 19:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260311_0004"
down_revision = "20260311_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signing_keys", sa.Column("revoked_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("signing_keys", "revoked_reason")
