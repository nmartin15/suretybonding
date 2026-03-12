"""
T2 — Notarization Evidence (PRD Section 10.2)

Verifies:
  1. notarization_meta is present and well-formed.
  2. Notary certificate is valid and not expired.
  3. RON video recording exists and checksum matches (if RON).
  4. Scanned pages exist and checksum matches (if wet-ink).
  5. Notarization timestamp <= manifest issued_at.
"""

import importlib.util
import os
from datetime import datetime

import pytest

from tests.support.helpers import sha256_hex

HAS_CRYPTO = importlib.util.find_spec("cryptography") is not None

try:
    import boto3

    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_s3_uri(uri: str) -> tuple[str, str]:
    """Parse s3://bucket/key into (bucket, key)."""
    assert uri.startswith("s3://"), f"Invalid S3 URI: {uri}"
    parts = uri[5:].split("/", 1)
    assert len(parts) == 2, f"Invalid S3 URI format: {uri}"
    return parts[0], parts[1]


def verify_s3_object(pointer: dict) -> None:
    """
    Verify an S3 object exists and its checksum matches the pointer.
    Requires boto3 and valid AWS credentials.
    """
    if not HAS_BOTO3:
        pytest.skip("boto3 not installed — cannot verify S3 objects")

    s3 = boto3.client("s3")
    bucket, key = parse_s3_uri(pointer["s3_uri"])

    # Head the object to verify existence and size
    head = s3.head_object(Bucket=bucket, Key=key)
    actual_size = head["ContentLength"]
    assert actual_size == pointer["size_bytes"], (
        f"S3 object size mismatch for {pointer['s3_uri']}.\n"
        f"  Expected: {pointer['size_bytes']}\n"
        f"  Actual:   {actual_size}"
    )

    # Download and verify checksum
    obj = s3.get_object(Bucket=bucket, Key=key)
    body = obj["Body"].read()
    actual_hash = sha256_hex(body)
    assert actual_hash == pointer["checksum_sha256"], (
        f"Checksum mismatch for {pointer['s3_uri']}.\n"
        f"  Expected: {pointer['checksum_sha256']}\n"
        f"  Actual:   {actual_hash}"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.acceptance
class TestT2NotarizationEvidence:
    """T2 acceptance test suite."""

    def test_notarization_meta_present(self, issued_manifest: dict):
        """Step 1: notarization_meta must be present with required fields."""
        nota = issued_manifest.get("notarization_meta")
        assert nota is not None, "notarization_meta is missing from manifest"

        required_fields = [
            "notarization_type",
            "notary_name",
            "notary_commission_id",
            "notary_state",
            "notarization_timestamp",
        ]
        missing = [f for f in required_fields if f not in nota]
        assert not missing, f"notarization_meta missing required fields: {missing}"

        assert nota["notarization_type"] in ("ron", "wet_ink"), (
            f"Invalid notarization_type: {nota['notarization_type']}"
        )

    @pytest.mark.skipif(not HAS_CRYPTO, reason="cryptography library not installed")
    def test_notary_certificate_valid(self, issued_manifest: dict):
        """Step 2: Notary X.509 certificate must be present and not expired."""
        nota = issued_manifest["notarization_meta"]

        if nota["notarization_type"] != "ron":
            pytest.skip("Notary certificate validation applies to RON only")

        cert_meta = nota.get("notary_certificate")
        assert cert_meta is not None, "notary_certificate missing for RON notarization"

        # Verify temporal validity
        not_before = datetime.fromisoformat(cert_meta["not_before"])
        not_after = datetime.fromisoformat(cert_meta["not_after"])
        nota_time = datetime.fromisoformat(nota["notarization_timestamp"])

        assert not_before <= nota_time <= not_after, (
            f"Notary certificate was not valid at notarization time.\n"
            f"  Certificate valid: {not_before} — {not_after}\n"
            f"  Notarization time: {nota_time}"
        )

        # Verify fingerprint is present
        assert "fingerprint_sha256" in cert_meta, (
            "notary_certificate.fingerprint_sha256 is missing"
        )

    def test_ron_video_evidence(self, issued_manifest: dict):
        """Step 3: RON video pointer must exist and checksum must match."""
        nota = issued_manifest["notarization_meta"]

        if nota["notarization_type"] != "ron":
            pytest.skip("RON video evidence check applies to RON only")

        assert "ron_session_id" in nota, "ron_session_id missing for RON notarization"
        assert "ron_video_pointer" in nota, "ron_video_pointer missing for RON notarization"

        pointer = nota["ron_video_pointer"]
        assert "s3_uri" in pointer, "ron_video_pointer.s3_uri is missing"
        assert "checksum_sha256" in pointer, "ron_video_pointer.checksum_sha256 is missing"
        assert "size_bytes" in pointer, "ron_video_pointer.size_bytes is missing"

        # Verify the actual S3 object if boto3 is available
        if os.getenv("VERIFY_S3_OBJECTS", "false").lower() == "true":
            verify_s3_object(pointer)

    def test_wet_ink_scanned_pages(self, issued_manifest: dict):
        """Step 4: Wet-ink scanned pages pointer must exist and checksum must match."""
        nota = issued_manifest["notarization_meta"]

        if nota["notarization_type"] != "wet_ink":
            pytest.skip("Scanned pages check applies to wet-ink only")

        assert "scanned_pages_pointer" in nota, (
            "scanned_pages_pointer missing for wet-ink notarization"
        )

        pointer = nota["scanned_pages_pointer"]
        assert "s3_uri" in pointer, "scanned_pages_pointer.s3_uri is missing"
        assert "checksum_sha256" in pointer, "scanned_pages_pointer.checksum_sha256 is missing"

        if os.getenv("VERIFY_S3_OBJECTS", "false").lower() == "true":
            verify_s3_object(pointer)

    def test_notarization_timestamp_before_issuance(self, issued_manifest: dict):
        """Step 5: notarization_timestamp must be <= issued_at."""
        nota_ts = datetime.fromisoformat(
            issued_manifest["notarization_meta"]["notarization_timestamp"]
        )
        issued_ts = datetime.fromisoformat(issued_manifest["issued_at"])

        assert nota_ts <= issued_ts, (
            f"Notarization occurred after issuance.\n"
            f"  notarization_timestamp = {nota_ts}\n"
            f"  issued_at              = {issued_ts}"
        )
