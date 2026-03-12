"""signing backend refactor

Revision ID: 20260311_0003
Revises: 20260311_0002
Create Date: 2026-03-11 18:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260311_0003"
down_revision = "20260311_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signing_keys", sa.Column("key_backend", sa.String(length=32), nullable=False, server_default="db_pem"))
    op.add_column("signing_keys", sa.Column("key_ref", sa.String(length=255), nullable=True))
    op.alter_column("signing_keys", "private_key_pem", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column("signing_keys", "private_key_pem", existing_type=sa.Text(), nullable=False)
    op.drop_column("signing_keys", "key_ref")
    op.drop_column("signing_keys", "key_backend")
