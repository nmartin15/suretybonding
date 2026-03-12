from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateBondRequest(BaseModel):
    principal_name: str
    principal_ubi_number: str
    contractor_registration_number: str
    obligee_agency_id: uuid.UUID
    contract_id: str
    contract_amount: str
    penal_sum: str
    project_description: str
    project_county: str
    carrier_id: uuid.UUID
    selected_clause_ids: list[uuid.UUID] = Field(default_factory=list)


class BondRequestOut(BaseModel):
    id: uuid.UUID
    status: str
    manifest_id: uuid.UUID | None = None
    status_history: list[dict]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ManifestOut(BaseModel):
    manifest_id: uuid.UUID
    bond_request_id: uuid.UUID
    document_hash: str
    ledger_entry_id: str
    ledger_hash: str
    manifest_json: dict
