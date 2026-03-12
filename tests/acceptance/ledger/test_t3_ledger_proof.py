"""
T3 — Ledger Proof (PRD Section 10.3)

Verifies:
  1. Ledger entry exists for the manifest's ledger_entry_id.
  2. Stored hash on ledger equals manifest's ledger_hash.
  3. Ledger timestamp <= manifest issued_at.
  4. Expected ledger_hash computed from manifest matches both sources.
"""

import pytest

from tests.support.api_client import ApiClient
from tests.support.helpers import compute_manifest_payload, sha256_hex


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.acceptance
class TestT3LedgerProof:
    """T3 acceptance test suite."""

    def test_ledger_fields_present(self, issued_manifest: dict):
        """Precondition: ledger_entry_id and ledger_hash must be present."""
        assert "ledger_entry_id" in issued_manifest, "ledger_entry_id missing from manifest"
        assert "ledger_hash" in issued_manifest, "ledger_hash missing from manifest"
        assert len(issued_manifest["ledger_hash"]) == 64, (
            f"ledger_hash should be 64 hex chars, got {len(issued_manifest['ledger_hash'])}"
        )

    def test_ledger_entry_exists_and_hash_matches(
        self, admin_client: ApiClient, issued_manifest: dict
    ):
        """Steps 1-2: Query ledger and confirm hash matches manifest."""
        manifest_id = issued_manifest["manifest_id"]

        # Use the verify endpoint which runs T1+T3 checks server-side
        resp = admin_client.get(f"/api/v1/manifests/{manifest_id}/verify")
        resp.raise_for_status()
        result = resp.json()

        # Find the ledger-specific checks
        checks_by_name = {c["check"]: c for c in result["checks"]}

        ledger_hash_check = checks_by_name.get("ledger_hash_match")
        assert ledger_hash_check is not None, (
            "Verification endpoint did not return ledger_hash_match check"
        )
        assert ledger_hash_check["result"] == "pass", (
            f"Ledger hash mismatch: {ledger_hash_check.get('detail', 'no detail')}"
        )

        ledger_ts_check = checks_by_name.get("ledger_timestamp_valid")
        assert ledger_ts_check is not None, (
            "Verification endpoint did not return ledger_timestamp_valid check"
        )
        assert ledger_ts_check["result"] == "pass", (
            f"Ledger timestamp invalid: {ledger_ts_check.get('detail', 'no detail')}"
        )

    def test_computed_ledger_hash_matches(self, issued_manifest: dict):
        """
        Step 4: Independently compute the expected ledger_hash and confirm
        it matches the manifest's ledger_hash field.

        The ledger_hash is SHA-256 of the manifest JSON excluding
        platform_signature, ledger_entry_id, and ledger_hash fields.
        """
        # Compute the payload (same as what gets signed and hashed for ledger)
        payload_bytes = compute_manifest_payload(issued_manifest)
        expected_hash = sha256_hex(payload_bytes)

        assert issued_manifest["ledger_hash"] == expected_hash, (
            f"Computed ledger hash does not match manifest.ledger_hash.\n"
            f"  manifest.ledger_hash = {issued_manifest['ledger_hash']}\n"
            f"  computed             = {expected_hash}\n"
            f"  payload_length       = {len(payload_bytes)} bytes"
        )
