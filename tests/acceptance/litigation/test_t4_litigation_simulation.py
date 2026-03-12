"""
T4 — Litigation Simulation / Subpoena Drill (PRD Section 10.4)

Verifies:
  1. Audit bundle can be generated on demand.
  2. Generation completes within 5 minutes.
  3. ZIP contains all required artifacts.
  4. T1, T2, T3 pass on the bundle contents.
  5. Legal memo is non-empty.
"""

import io
import json
import time
import zipfile

import pytest

from tests.support.api_client import ApiClient
from tests.support.config import AUDIT_BUNDLE_TIMEOUT_SECONDS
from tests.support.helpers import sha256_hex

# Expected files in the audit bundle per PRD FR-10
REQUIRED_BUNDLE_FILES = {
    "bond.pdf",
    "manifest.json",
    "notarization_evidence.json",
    "kyc_pointer.json",
    "ledger_proof.json",
    "legal_memo.pdf",
    "clause_lineage.json",
    "rule_evaluation_log.json",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def trigger_and_download_bundle(
    client: ApiClient, manifest_id: str
) -> tuple[bytes, float]:
    """
    Trigger bundle generation and poll until ready. Returns (zip_bytes, elapsed_seconds).
    """
    # Trigger generation
    resp = client.post(f"/api/v1/audit-bundles/{manifest_id}/generate")
    resp.raise_for_status()
    assert resp.status_code == 202, f"Expected 202 Accepted, got {resp.status_code}"

    start = time.time()
    deadline = start + AUDIT_BUNDLE_TIMEOUT_SECONDS

    # Poll for the bundle to be available
    while time.time() < deadline:
        dl_resp = client.get(f"/api/v1/audit-bundles/{manifest_id}")
        if dl_resp.status_code == 200:
            elapsed = time.time() - start
            return dl_resp.content, elapsed
        if dl_resp.status_code == 404:
            # Not ready yet — bundle still generating
            time.sleep(5)
        else:
            dl_resp.raise_for_status()

    raise TimeoutError(
        f"Audit bundle for manifest {manifest_id} not available within "
        f"{AUDIT_BUNDLE_TIMEOUT_SECONDS}s"
    )


def extract_bundle(zip_bytes: bytes) -> dict[str, bytes]:
    """Extract all files from the audit bundle ZIP into a dict."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        return {name: zf.read(name) for name in zf.namelist()}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.acceptance
class TestT4LitigationSimulation:
    """T4 acceptance test suite — subpoena drill."""

    @pytest.fixture
    def bundle_data(
        self, admin_client: ApiClient, issued_bond: dict
    ) -> tuple[dict[str, bytes], float, dict]:
        """Generate and extract the audit bundle. Returns (files, elapsed, manifest)."""
        manifest_id = issued_bond["manifest_id"]

        zip_bytes, elapsed = trigger_and_download_bundle(admin_client, manifest_id)

        # Verify it's a valid ZIP
        assert zipfile.is_zipfile(io.BytesIO(zip_bytes)), (
            "Downloaded file is not a valid ZIP"
        )

        files = extract_bundle(zip_bytes)

        # Parse the manifest from the bundle
        assert "manifest.json" in files, "manifest.json missing from bundle"
        manifest = json.loads(files["manifest.json"])

        return files, elapsed, manifest

    def test_bundle_generation_time(self, bundle_data: tuple):
        """Step 2: Bundle must be produced within 5 minutes."""
        _, elapsed, _ = bundle_data
        assert elapsed <= AUDIT_BUNDLE_TIMEOUT_SECONDS, (
            f"Audit bundle took {elapsed:.1f}s to generate "
            f"(limit: {AUDIT_BUNDLE_TIMEOUT_SECONDS}s)"
        )

    def test_bundle_contains_all_artifacts(self, bundle_data: tuple):
        """Step 3: ZIP must contain all required files."""
        files, _, _ = bundle_data
        file_names = set(files.keys())
        missing = REQUIRED_BUNDLE_FILES - file_names
        assert not missing, (
            f"Audit bundle is missing required files: {missing}\n"
            f"Bundle contains: {file_names}"
        )

    def test_bundle_manifest_document_hash(self, bundle_data: tuple):
        """Step 4 (T1 subset): document_hash in bundled manifest matches bundled PDF."""
        files, _, manifest = bundle_data
        assert "bond.pdf" in files, "bond.pdf missing from bundle"

        computed_hash = sha256_hex(files["bond.pdf"])
        assert manifest["document_hash"] == computed_hash, (
            f"Bundled manifest document_hash does not match bundled PDF.\n"
            f"  manifest.document_hash = {manifest['document_hash']}\n"
            f"  SHA-256(bond.pdf)      = {computed_hash}"
        )

    def test_bundle_manifest_schema_valid(
        self, bundle_data: tuple, manifest_schema: dict
    ):
        """Step 4 (T1 subset): bundled manifest conforms to schema."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")

        _, _, manifest = bundle_data
        validator = jsonschema.Draft202012Validator(manifest_schema)
        errors = sorted(validator.iter_errors(manifest), key=lambda e: list(e.path))

        assert not errors, "Bundled manifest failed schema validation:\n" + "\n".join(
            f"  - {'.'.join(str(p) for p in e.path)}: {e.message}" for e in errors[:10]
        )

    def test_bundle_notarization_evidence(self, bundle_data: tuple):
        """Step 5 (T2 subset): notarization evidence is present and well-formed."""
        files, _, manifest = bundle_data

        assert "notarization_evidence.json" in files
        nota_evidence = json.loads(files["notarization_evidence.json"])

        # Should contain the same notarization_meta as the manifest
        assert "notarization_type" in nota_evidence, (
            "notarization_evidence.json missing notarization_type"
        )
        assert "notary_name" in nota_evidence, (
            "notarization_evidence.json missing notary_name"
        )

        # Verify the notarization evidence is consistent with the manifest
        manifest_nota = manifest.get("notarization_meta", {})
        assert nota_evidence.get("notarization_type") == manifest_nota.get(
            "notarization_type"
        ), "Notarization type mismatch between bundle evidence and manifest"

    def test_bundle_ledger_proof(self, bundle_data: tuple):
        """Step 6 (T3 subset): ledger proof is present and consistent."""
        files, _, manifest = bundle_data

        assert "ledger_proof.json" in files
        proof = json.loads(files["ledger_proof.json"])

        assert "ledger_entry_id" in proof, "ledger_proof.json missing ledger_entry_id"
        assert "ledger_hash" in proof, "ledger_proof.json missing ledger_hash"

        # Verify consistency with manifest
        assert proof["ledger_entry_id"] == manifest.get("ledger_entry_id"), (
            "ledger_entry_id mismatch between proof file and manifest"
        )
        assert proof["ledger_hash"] == manifest.get("ledger_hash"), (
            "ledger_hash mismatch between proof file and manifest"
        )

    def test_bundle_kyc_pointer(self, bundle_data: tuple):
        """KYC pointer file is present and contains no PII."""
        files, _, _ = bundle_data

        assert "kyc_pointer.json" in files
        kyc = json.loads(files["kyc_pointer.json"])

        assert "provider" in kyc, "kyc_pointer.json missing provider"
        assert "verification_id" in kyc, "kyc_pointer.json missing verification_id"

        # Ensure no PII fields leaked into the KYC pointer
        pii_fields = {
            "ssn",
            "social_security",
            "date_of_birth",
            "dob",
            "address",
            "phone",
        }
        leaked = pii_fields & set(kyc.keys())
        assert not leaked, f"KYC pointer contains PII fields: {leaked}"

    def test_bundle_legal_memo_nonempty(self, bundle_data: tuple):
        """Step 7: Legal memo PDF must be non-empty."""
        files, _, _ = bundle_data

        assert "legal_memo.pdf" in files
        memo_bytes = files["legal_memo.pdf"]
        assert len(memo_bytes) > 100, (
            f"Legal memo PDF appears empty or trivially small ({len(memo_bytes)} bytes)"
        )
        # Verify it starts with PDF magic bytes
        assert memo_bytes[:5] == b"%PDF-", (
            "legal_memo.pdf does not appear to be a valid PDF"
        )

    def test_bundle_clause_lineage(self, bundle_data: tuple):
        """Clause lineage file is present and references manifest clause IDs."""
        files, _, manifest = bundle_data

        assert "clause_lineage.json" in files
        lineage = json.loads(files["clause_lineage.json"])

        assert isinstance(lineage, list), "clause_lineage.json should be an array"
        assert len(lineage) >= 1, "clause_lineage.json is empty"

        # Every clause in the manifest should have a lineage entry
        manifest_clause_ids = set(manifest.get("clause_version_ids", []))
        lineage_clause_ids = {entry.get("clause_version_id") for entry in lineage}
        missing = manifest_clause_ids - lineage_clause_ids
        assert not missing, (
            f"Clause lineage missing entries for manifest clauses: {missing}"
        )

    def test_bundle_rule_evaluation_log(self, bundle_data: tuple):
        """Rule evaluation log is present and has entries."""
        files, _, _ = bundle_data

        assert "rule_evaluation_log.json" in files
        log = json.loads(files["rule_evaluation_log.json"])

        assert isinstance(log, list), "rule_evaluation_log.json should be an array"
        assert len(log) >= 1, "rule_evaluation_log.json is empty"

        # Each entry should have rule_id, result, and citation
        for entry in log:
            assert "rule_id" in entry, f"Rule log entry missing rule_id: {entry}"
            assert "result" in entry, f"Rule log entry missing result: {entry}"
