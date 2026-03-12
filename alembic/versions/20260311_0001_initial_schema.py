"""initial schema

Revision ID: 20260311_0001
Revises:
Create Date: 2026-03-11 17:25:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260311_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bond_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("principal_name", sa.String(length=255), nullable=False),
        sa.Column("principal_ubi_number", sa.String(length=64), nullable=False),
        sa.Column("contractor_registration_number", sa.String(length=64), nullable=False),
        sa.Column("obligee_agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("carrier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("broker_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_id", sa.String(length=128), nullable=False),
        sa.Column("contract_amount", sa.String(length=32), nullable=False),
        sa.Column("penal_sum", sa.String(length=32), nullable=False),
        sa.Column("project_description", sa.Text(), nullable=False),
        sa.Column("project_county", sa.String(length=64), nullable=False),
        sa.Column("selected_clause_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("status_history", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("bond_pdf", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bond_requests_broker_id"), "bond_requests", ["broker_id"], unique=False)
    op.create_index(op.f("ix_bond_requests_status"), "bond_requests", ["status"], unique=False)

    op.create_table(
        "manifests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bond_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_hash", sa.String(length=64), nullable=False),
        sa.Column("ledger_entry_id", sa.String(length=255), nullable=False),
        sa.Column("ledger_hash", sa.String(length=64), nullable=False),
        sa.Column("manifest_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bond_request_id"], ["bond_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bond_request_id"),
    )
    op.create_index(op.f("ix_manifests_bond_request_id"), "manifests", ["bond_request_id"], unique=True)
    op.create_index(op.f("ix_manifests_document_hash"), "manifests", ["document_hash"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_manifests_document_hash"), table_name="manifests")
    op.drop_index(op.f("ix_manifests_bond_request_id"), table_name="manifests")
    op.drop_table("manifests")
    op.drop_index(op.f("ix_bond_requests_status"), table_name="bond_requests")
    op.drop_index(op.f("ix_bond_requests_broker_id"), table_name="bond_requests")
    op.drop_table("bond_requests")
