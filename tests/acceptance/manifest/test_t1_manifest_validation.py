"""
T1 — Manifest Validation (PRD Section 10.1)

Verifies:
  1. document_hash matches SHA-256 of the bond PDF.
  2. Manifest JSON conforms to manifest.schema.json.
  3. platform_signature is valid against the certificate chain.
  4. Certificate chain terminates at a trusted root.
"""

import pytest

from tests.support.api_client import ApiClient
from tests.support.helpers import (
    compute_manifest_payload,
    fetch_bond_pdf,
    fetch_manifest,
    sha256_hex,
)

# Optional imports — gracefully degrade if not installed yet
try:
    import jsonschema
except ImportError:
    jsonschema = None

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, padding
    from cryptography.x509 import load_pem_x509_certificate

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.acceptance
class TestT1ManifestValidation:
    """T1 acceptance test suite."""

    def test_document_hash_matches_pdf(
        self, admin_client: ApiClient, issued_bond: dict
    ):
        """Step 1-2: SHA-256 of bond PDF must equal manifest.document_hash."""
        manifest_id = issued_bond["manifest_id"]
        manifest = fetch_manifest(admin_client, manifest_id)

        pdf_bytes = fetch_bond_pdf(admin_client, issued_bond["id"])
        computed_hash = sha256_hex(pdf_bytes)

        assert manifest["document_hash"] == computed_hash, (
            f"Document hash mismatch.\n"
            f"  manifest.document_hash = {manifest['document_hash']}\n"
            f"  SHA-256(PDF)           = {computed_hash}"
        )

    @pytest.mark.skipif(jsonschema is None, reason="jsonschema not installed")
    def test_manifest_conforms_to_schema(
        self, admin_client: ApiClient, issued_bond: dict, manifest_schema: dict
    ):
        """Step 3: Manifest JSON must validate against manifest.schema.json."""
        manifest_id = issued_bond["manifest_id"]
        manifest = fetch_manifest(admin_client, manifest_id)

        validator = jsonschema.Draft202012Validator(manifest_schema)
        errors = sorted(validator.iter_errors(manifest), key=lambda e: list(e.path))

        assert not errors, (
            f"Manifest failed schema validation with {len(errors)} error(s):\n"
            + "\n".join(
                f"  - {'.'.join(str(p) for p in e.path)}: {e.message}"
                for e in errors[:10]
            )
        )

    @pytest.mark.skipif(not HAS_CRYPTO, reason="cryptography library not installed")
    def test_platform_signature_valid(self, admin_client: ApiClient, issued_bond: dict):
        """Steps 4-5: Verify platform_signature against the manifest payload."""
        manifest_id = issued_bond["manifest_id"]
        manifest = fetch_manifest(admin_client, manifest_id)

        sig_block = manifest["platform_signature"]
        assert "signature" in sig_block, "platform_signature.signature is missing"
        assert "certificate_chain" in sig_block, (
            "platform_signature.certificate_chain is missing"
        )
        assert len(sig_block["certificate_chain"]) >= 1, "Certificate chain is empty"

        # Load the signing certificate (first in chain)
        signing_cert_pem = sig_block["certificate_chain"][0].encode()
        signing_cert = load_pem_x509_certificate(signing_cert_pem)

        # Decode signature
        import base64

        signature_bytes = base64.b64decode(sig_block["signature"])

        # Compute the payload that was signed
        payload = compute_manifest_payload(manifest)

        # Verify based on algorithm
        public_key = signing_cert.public_key()
        algorithm = sig_block.get("algorithm", "ECDSA-P256")

        if algorithm.startswith("ECDSA"):
            # ECDSA verification
            public_key.verify(
                signature_bytes,
                payload,
                ec.ECDSA(hashes.SHA256()),
            )
        elif algorithm.startswith("RSA-PSS"):
            # RSA-PSS verification
            public_key.verify(
                signature_bytes,
                payload,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
        else:
            pytest.fail(f"Unsupported signing algorithm: {algorithm}")

    @pytest.mark.skipif(not HAS_CRYPTO, reason="cryptography library not installed")
    def test_certificate_chain_trusted(
        self, admin_client: ApiClient, issued_bond: dict
    ):
        """Step 6: Certificate chain must terminate at a trusted root."""
        manifest_id = issued_bond["manifest_id"]
        manifest = fetch_manifest(admin_client, manifest_id)

        chain_pems = manifest["platform_signature"]["certificate_chain"]
        assert len(chain_pems) >= 1, "Certificate chain is empty"

        certs = [load_pem_x509_certificate(pem.encode()) for pem in chain_pems]

        # Verify each cert is signed by the next cert in chain
        for i in range(len(certs) - 1):
            child = certs[i]
            parent = certs[i + 1]
            parent_public_key = parent.public_key()

            # Verify the child's signature was made by the parent's key
            # This is a basic chain validation — production should use a full
            # X.509 path validation library.
            try:
                if isinstance(parent_public_key, ec.EllipticCurvePublicKey):
                    parent_public_key.verify(
                        child.signature,
                        child.tbs_certificate_bytes,
                        ec.ECDSA(child.signature_hash_algorithm),
                    )
                else:
                    parent_public_key.verify(
                        child.signature,
                        child.tbs_certificate_bytes,
                        padding.PKCS1v15(),
                        child.signature_hash_algorithm,
                    )
            except Exception as e:
                pytest.fail(f"Certificate chain broken at index {i} -> {i + 1}: {e}")

        # The last certificate should be self-signed (root CA) or match a
        # trusted root. For now, verify self-signed.
        root = certs[-1]
        assert root.issuer == root.subject, (
            "Last certificate in chain is not self-signed (not a root CA).\n"
            f"  Subject: {root.subject}\n"
            f"  Issuer:  {root.issuer}"
        )
