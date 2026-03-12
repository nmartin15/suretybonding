import json

import pytest

from tests.support.helpers import (
    compute_manifest_payload,
    fetch_bond_pdf,
    fetch_manifest,
    sha256_hex,
)

pytestmark = pytest.mark.unit


def test_sha256_hex_known_value():
    assert sha256_hex(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223"
        "b00361a396177a9cb410ff61f20015ad"
    )


def test_compute_manifest_payload_excludes_non_signable_fields():
    manifest = {
        "manifest_id": "m-1",
        "document_hash": "deadbeef",
        "platform_signature": {"signature": "sig"},
        "ledger_entry_id": "l-1",
        "ledger_hash": "h-1",
    }

    payload_bytes = compute_manifest_payload(manifest)
    payload = json.loads(payload_bytes.decode())

    assert "platform_signature" not in payload
    assert "ledger_entry_id" not in payload
    assert "ledger_hash" not in payload
    assert payload["manifest_id"] == "m-1"
    assert payload["document_hash"] == "deadbeef"


def test_compute_manifest_payload_is_deterministic_for_key_order():
    manifest_a = {"b": 2, "a": 1}
    manifest_b = {"a": 1, "b": 2}
    assert compute_manifest_payload(manifest_a) == compute_manifest_payload(manifest_b)


class _FakeResponse:
    def __init__(self, payload: dict | None = None, content: bytes | None = None):
        self._payload = payload or {}
        self.content = content or b""

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, response: _FakeResponse):
        self.response = response
        self.paths: list[str] = []

    def get(self, path: str):
        self.paths.append(path)
        return self.response


def test_fetch_manifest_uses_manifest_endpoint():
    fake = _FakeClient(_FakeResponse(payload={"manifest_id": "m-123"}))
    manifest = fetch_manifest(fake, "m-123")

    assert fake.paths == ["/api/v1/manifests/m-123"]
    assert manifest["manifest_id"] == "m-123"


def test_fetch_bond_pdf_uses_pdf_endpoint():
    fake = _FakeClient(_FakeResponse(content=b"%PDF-sample"))
    pdf_bytes = fetch_bond_pdf(fake, "b-123")

    assert fake.paths == ["/api/v1/bonds/b-123/pdf"]
    assert pdf_bytes.startswith(b"%PDF-")
