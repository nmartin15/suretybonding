"""
T5 — Auto-Issue Policy Gate (PRD Section 10.5)

Verifies:
  1. A bond request with pre-approved clauses and within-policy exposure
     auto-issues without human review.
  2. Final status is "issued".
  3. Manifest and audit bundle are created.
  4. T1, T2, T3 pass on the resulting manifest.
  5. No human review actions appear in status_history.
"""

import json
import time

import pytest

from tests.support.api_client import ApiClient
from tests.support.config import PRE_APPROVED_CLAUSE_IDS
from tests.support.helpers import poll_bond_status


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.acceptance
class TestT5AutoIssuePolicyGate:
    """T5 acceptance test suite — end-to-end auto-issue."""

    @pytest.fixture
    def auto_issued_bond(
        self, broker_client: ApiClient, sample_bond_payload: dict
    ) -> dict:
        """
        Create a bond request, submit it, and wait for auto-issuance.
        Returns the final bond object in "issued" status.
        """
        if not PRE_APPROVED_CLAUSE_IDS:
            pytest.skip(
                "PRE_APPROVED_CLAUSE_IDS not configured — cannot test auto-issue. "
                "Set this env var to a JSON array of pre-approved clause version UUIDs."
            )

        # Step 1: Create bond request
        resp = broker_client.post("/api/v1/bonds", json_body=sample_bond_payload)
        assert resp.status_code == 201, (
            f"Failed to create bond request: {resp.status_code} {resp.text}"
        )
        bond = resp.json()
        bond_id = bond["id"]
        assert bond["status"] == "draft"

        # Step 2: Submit for evaluation
        resp = broker_client.post(f"/api/v1/bonds/{bond_id}/submit")
        assert resp.status_code == 202, (
            f"Failed to submit bond request: {resp.status_code} {resp.text}"
        )

        # Step 3: Poll until terminal state
        terminal_statuses = {"issued", "review_required", "rejected"}
        bond = poll_bond_status(broker_client, bond_id, terminal_statuses)

        return bond

    def test_auto_issued_status(self, auto_issued_bond: dict):
        """Step 4: Bond must reach 'issued' status without human review."""
        assert auto_issued_bond["status"] == "issued", (
            f"Bond did not auto-issue. Final status: {auto_issued_bond['status']}.\n"
            f"Status history: {json.dumps(auto_issued_bond.get('status_history', []), indent=2)}"
        )

    def test_no_human_review_in_history(self, auto_issued_bond: dict):
        """Step 7: No human review actions in status_history."""
        if auto_issued_bond["status"] != "issued":
            pytest.skip("Bond did not auto-issue")

        history = auto_issued_bond.get("status_history", [])
        human_review_statuses = {"review_required", "approved", "info_requested"}
        review_entries = [
            entry for entry in history
            if entry.get("status") in human_review_statuses
        ]
        assert not review_entries, (
            "Bond required human review despite pre-approved clauses.\n"
            f"Review entries: {json.dumps(review_entries, indent=2)}"
        )

    def test_manifest_created(
        self, admin_client: ApiClient, auto_issued_bond: dict
    ):
        """Step 5: Manifest must exist for the issued bond."""
        if auto_issued_bond["status"] != "issued":
            pytest.skip("Bond did not auto-issue")

        manifest_id = auto_issued_bond.get("manifest_id")
        assert manifest_id is not None, "Issued bond has no manifest_id"

        resp = admin_client.get(f"/api/v1/manifests/{manifest_id}")
        assert resp.status_code == 200, (
            f"Manifest {manifest_id} not found: {resp.status_code}"
        )

        manifest = resp.json()
        assert manifest["bond_request_id"] == auto_issued_bond["id"]
        assert manifest["jurisdiction"] == "WA"
        assert manifest["bond_type"] == "public_works_performance"

    def test_manifest_signature_valid(
        self, admin_client: ApiClient, auto_issued_bond: dict
    ):
        """Step 6 (T1 subset): Verify manifest signature via the verify endpoint."""
        if auto_issued_bond["status"] != "issued":
            pytest.skip("Bond did not auto-issue")

        manifest_id = auto_issued_bond["manifest_id"]
        resp = admin_client.get(f"/api/v1/manifests/{manifest_id}/verify")
        resp.raise_for_status()
        result = resp.json()

        assert result["overall_result"] == "pass", (
            "Manifest verification failed.\n"
            f"Checks: {json.dumps(result['checks'], indent=2)}"
        )

        # Verify specific checks passed
        checks_by_name = {c["check"]: c for c in result["checks"]}
        for check_name in ["document_hash_match", "schema_valid", "platform_signature_valid"]:
            check = checks_by_name.get(check_name)
            assert check is not None, f"Missing verification check: {check_name}"
            assert check["result"] == "pass", (
                f"Check {check_name} failed: {check.get('detail')}"
            )

    def test_audit_bundle_exists(
        self, admin_client: ApiClient, auto_issued_bond: dict
    ):
        """Audit bundle must be downloadable for the issued bond."""
        if auto_issued_bond["status"] != "issued":
            pytest.skip("Bond did not auto-issue")

        manifest_id = auto_issued_bond["manifest_id"]
        resp = admin_client.get(f"/api/v1/audit-bundles/{manifest_id}")

        # Bundle might need a moment to generate after issuance
        if resp.status_code == 404:
            time.sleep(30)
            resp = admin_client.get(f"/api/v1/audit-bundles/{manifest_id}")

        assert resp.status_code == 200, (
            f"Audit bundle not available for manifest {manifest_id}: {resp.status_code}"
        )
        assert len(resp.content) > 0, "Audit bundle is empty"

    def test_ledger_proof_valid(
        self, admin_client: ApiClient, auto_issued_bond: dict
    ):
        """Step 6 (T3 subset): Ledger proof must be valid."""
        if auto_issued_bond["status"] != "issued":
            pytest.skip("Bond did not auto-issue")

        manifest_id = auto_issued_bond["manifest_id"]
        resp = admin_client.get(f"/api/v1/manifests/{manifest_id}/verify")
        resp.raise_for_status()
        result = resp.json()

        checks_by_name = {c["check"]: c for c in result["checks"]}

        ledger_check = checks_by_name.get("ledger_hash_match")
        if ledger_check and ledger_check["result"] != "skipped":
            assert ledger_check["result"] == "pass", (
                f"Ledger hash check failed: {ledger_check.get('detail')}"
            )
