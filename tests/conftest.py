"""Shared fixtures for the E-Bonding acceptance test suite (T1–T6)."""

import json
import os

import pytest

from tests.support.api_client import ApiClient
from tests.support.config import (
    ADMIN2_TOKEN,
    ADMIN_APPROVAL_TOKEN,
    ADMIN_TOKEN,
    BASE_URL,
    BROKER_TOKEN,
    MANIFEST_SCHEMA_PATH,
    PILOT_CARRIER_ID,
    PILOT_OBLIGEE_ID,
    PRE_APPROVED_CLAUSE_IDS,
    UNDERWRITER_TOKEN,
)
from tests.support.helpers import fetch_manifest

@pytest.fixture(scope="session")
def admin_client() -> ApiClient:
    return ApiClient(base_url=BASE_URL, token=ADMIN_TOKEN)


@pytest.fixture(scope="session")
def admin2_client() -> ApiClient:
    return ApiClient(base_url=BASE_URL, token=ADMIN2_TOKEN)


@pytest.fixture(scope="session")
def admin_approval_token() -> str:
    return ADMIN_APPROVAL_TOKEN


@pytest.fixture(scope="session")
def broker_client() -> ApiClient:
    return ApiClient(base_url=BASE_URL, token=BROKER_TOKEN)


@pytest.fixture(scope="session")
def underwriter_client() -> ApiClient:
    return ApiClient(base_url=BASE_URL, token=UNDERWRITER_TOKEN)


@pytest.fixture(scope="session")
def manifest_schema() -> dict:
    """Load manifest.schema.json for validation."""
    with open(MANIFEST_SCHEMA_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def sample_bond_payload() -> dict:
    """
    Minimal valid bond request payload for the pilot agency.
    Uses pre-approved clause IDs so T5 can auto-issue.
    """
    return {
        "principal_name": "Acceptance Test Contractor LLC",
        "principal_ubi_number": "600000001",
        "contractor_registration_number": "TESTCR001",
        "obligee_agency_id": PILOT_OBLIGEE_ID,
        "contract_id": "TEST-CONTRACT-001",
        "contract_amount": "500000.00",
        "penal_sum": "500000.00",
        "project_description": "Acceptance test project — WA public works performance bond.",
        "project_county": "King",
        "carrier_id": PILOT_CARRIER_ID,
        "selected_clause_ids": PRE_APPROVED_CLAUSE_IDS,
    }


@pytest.fixture
def issued_bond(broker_client: ApiClient) -> dict:
    """
    Retrieve a previously issued bond for T1/T2/T3 testing.
    Expects ISSUED_BOND_ID in the environment. If not set, skips.
    """
    bond_id = os.getenv("ISSUED_BOND_ID")
    if not bond_id:
        pytest.skip("ISSUED_BOND_ID not set — no pre-issued bond available for testing.")
    resp = broker_client.get(f"/api/v1/bonds/{bond_id}")
    resp.raise_for_status()
    bond = resp.json()
    assert bond["status"] == "issued", f"Expected issued bond, got status={bond['status']}"
    return bond


@pytest.fixture
def issued_manifest(admin_client: ApiClient, issued_bond: dict) -> dict:
    """Fetch manifest corresponding to the issued bond fixture."""
    return fetch_manifest(admin_client, issued_bond["manifest_id"])
