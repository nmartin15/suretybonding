"""create signing key operation request table

Revision ID: 20260311_0006
Revises: 20260311_0005
Create Date: 2026-03-11 20:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260311_0006"
down_revision = "20260311_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signing_key_operation_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_type", sa.String(length=32), nullable=False),
        sa.Column("target_key_id", sa.String(length=128), nullable=True),
        sa.Column("backend", sa.String(length=32), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("emergency", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("create_replacement", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("approval_token_hash", sa.String(length=64), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("execution_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_signing_key_operation_requests_operation_type"), "signing_key_operation_requests", ["operation_type"], unique=False)
    op.create_index(op.f("ix_signing_key_operation_requests_requested_by"), "signing_key_operation_requests", ["requested_by"], unique=False)
    op.create_index(op.f("ix_signing_key_operation_requests_approved_by"), "signing_key_operation_requests", ["approved_by"], unique=False)
    op.create_index(op.f("ix_signing_key_operation_requests_status"), "signing_key_operation_requests", ["status"], unique=False)
    op.create_index(op.f("ix_signing_key_operation_requests_created_at"), "signing_key_operation_requests", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_signing_key_operation_requests_created_at"), table_name="signing_key_operation_requests")
    op.drop_index(op.f("ix_signing_key_operation_requests_status"), table_name="signing_key_operation_requests")
    op.drop_index(op.f("ix_signing_key_operation_requests_approved_by"), table_name="signing_key_operation_requests")
    op.drop_index(op.f("ix_signing_key_operation_requests_requested_by"), table_name="signing_key_operation_requests")
    op.drop_index(op.f("ix_signing_key_operation_requests_operation_type"), table_name="signing_key_operation_requests")
    op.drop_table("signing_key_operation_requests")
