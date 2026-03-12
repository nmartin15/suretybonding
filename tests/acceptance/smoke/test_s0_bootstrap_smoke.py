"""S0 smoke test: basic runtime viability for release-candidate checks."""

from __future__ import annotations

import uuid

import pytest

from tests.support.api_client import ApiClient


@pytest.mark.acceptance
def test_s0_runtime_smoke(
    admin_client: ApiClient,
    admin2_client: ApiClient,
    admin_approval_token: str,
) -> None:
    health = admin_client.get("/api/v1/health")
    health.raise_for_status()
    assert health.json().get("status") == "ok"

    rotate_request = admin_client.post(
        "/api/v1/admin/signing-keys/rotate",
        json_body={
            "reason": f"smoke rotation {uuid.uuid4()}",
            "approval_token": admin_approval_token,
        },
    )
    rotate_request.raise_for_status()
    assert rotate_request.status_code == 202
    request_id = rotate_request.json()["request"]["id"]

    approve = admin2_client.post(
        f"/api/v1/admin/signing-key-operation-requests/{request_id}/approve",
        json_body={"approval_token": admin_approval_token},
    )
    approve.raise_for_status()
    body = approve.json()
    assert body["status"] == "executed"
