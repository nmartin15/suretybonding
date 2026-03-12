from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BondRequest(Base):
    __tablename__ = "bond_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    principal_name: Mapped[str] = mapped_column(String(255))
    principal_ubi_number: Mapped[str] = mapped_column(String(64))
    contractor_registration_number: Mapped[str] = mapped_column(String(64))
    obligee_agency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    carrier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    broker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    contract_id: Mapped[str] = mapped_column(String(128))
    contract_amount: Mapped[str] = mapped_column(String(32))
    penal_sum: Mapped[str] = mapped_column(String(32))
    project_description: Mapped[str] = mapped_column(Text)
    project_county: Mapped[str] = mapped_column(String(64))
    selected_clause_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    status_history: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    bond_pdf: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    manifest: Mapped["Manifest | None"] = relationship(
        back_populates="bond", uselist=False
    )


class Manifest(Base):
    __tablename__ = "manifests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bond_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bond_requests.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    document_hash: Mapped[str] = mapped_column(String(64), index=True)
    ledger_entry_id: Mapped[str] = mapped_column(String(255))
    ledger_hash: Mapped[str] = mapped_column(String(64))
    manifest_json: Mapped[dict] = mapped_column(JSONB)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    bond: Mapped[BondRequest] = relationship(back_populates="manifest")


class SigningKey(Base):
    __tablename__ = "signing_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    key_backend: Mapped[str] = mapped_column(String(32), default="db_pem")
    key_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    private_key_pem: Mapped[str | None] = mapped_column(Text, nullable=True)
    certificate_pem: Mapped[str] = mapped_column(Text)
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    not_after: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class SigningKeyEvent(Base):
    __tablename__ = "signing_key_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    action: Mapped[str] = mapped_column(String(32), index=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    reason: Mapped[str] = mapped_column(Text)
    old_key_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    new_key_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_emergency: Mapped[bool] = mapped_column(default=False)
    approval_token_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )


class SigningKeyOperationRequest(Base):
    __tablename__ = "signing_key_operation_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    operation_type: Mapped[str] = mapped_column(String(32), index=True)
    target_key_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    backend: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    emergency: Mapped[bool] = mapped_column(default=False)
    create_replacement: Mapped[bool] = mapped_column(default=False)
    approval_token_hash: Mapped[str] = mapped_column(String(64))
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    execution_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
