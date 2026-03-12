import hashlib
import json
import time
from typing import Any

from tests.support.api_client import ApiClient
from tests.support.config import AUTO_ISSUE_TIMEOUT_SECONDS, POLL_INTERVAL_SECONDS


def sha256_hex(data: bytes) -> str:
    """Compute lowercase hex SHA-256 digest."""
    return hashlib.sha256(data).hexdigest()


def poll_bond_status(
    client: ApiClient,
    bond_id: str,
    terminal_statuses: set[str],
    timeout: int = AUTO_ISSUE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Poll GET /api/v1/bonds/{id} until status is in terminal_statuses or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/v1/bonds/{bond_id}")
        resp.raise_for_status()
        bond = resp.json()
        if bond["status"] in terminal_statuses:
            return bond
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(
        f"Bond {bond_id} did not reach {terminal_statuses} within {timeout}s. "
        f"Last status: {bond.get('status')}"
    )


def fetch_manifest(client: ApiClient, manifest_id: str) -> dict:
    """GET /api/v1/manifests/{id} and return parsed JSON."""
    resp = client.get(f"/api/v1/manifests/{manifest_id}")
    resp.raise_for_status()
    return resp.json()


def fetch_bond_pdf(client: ApiClient, bond_id: str) -> bytes:
    """
    Download the signed bond PDF.
    Assumes the bond PDF is available at /api/v1/bonds/{id}/pdf or via the
    audit bundle. Adjust the endpoint once document serving is implemented.
    """
    # TODO: Replace with actual bond PDF download endpoint once implemented.
    resp = client.get(f"/api/v1/bonds/{bond_id}/pdf")
    resp.raise_for_status()
    return resp.content


def compute_manifest_payload(manifest: dict) -> bytes:
    """
    Compute the signable payload: manifest JSON minus platform_signature,
    ledger_entry_id, and ledger_hash fields (per PRD FR-06).
    """
    payload = {
        k: v
        for k, v in manifest.items()
        if k not in ("platform_signature", "ledger_entry_id", "ledger_hash")
    }
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
