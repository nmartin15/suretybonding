"""
T6 — Signing key dual-control workflow

Verifies:
  1. Admin A can create key operation requests.
  2. Requester cannot approve their own request.
  3. Admin B can approve and execute the request.
  4. Execution emits immutable signing key events.
"""

import pytest

from tests.support.api_client import ApiClient


@pytest.mark.acceptance
class TestT6SigningKeyDualControl:
    """Dual-admin request/approval controls for key operations."""

    def test_rotate_request_requires_second_admin_approval(
        self,
        admin_client: ApiClient,
        admin2_client: ApiClient,
        admin_approval_token: str,
    ):
        # Admin A creates request
        create_resp = admin_client.post(
            "/api/v1/admin/signing-keys/rotate",
            json_body={
                "reason": "dual-control test rotation",
                "approval_token": admin_approval_token,
            },
        )
        create_resp.raise_for_status()
        assert create_resp.status_code == 202
        req = create_resp.json()["request"]
        request_id = req["id"]

        # Same admin cannot approve own request
        same_admin_approve = admin_client.post(
            f"/api/v1/admin/signing-key-operation-requests/{request_id}/approve",
            json_body={"approval_token": admin_approval_token},
        )
        assert same_admin_approve.status_code == 409

        # Different admin approves successfully
        approve_resp = admin2_client.post(
            f"/api/v1/admin/signing-key-operation-requests/{request_id}/approve",
            json_body={"approval_token": admin_approval_token},
        )
        approve_resp.raise_for_status()
        body = approve_resp.json()
        assert body["status"] == "executed"
        assert body["request"]["status"] == "executed"
        assert body["request"]["approved_by"] is not None
        assert body["execution_result"]["status"] == "rotated"

    def test_key_event_written_after_execution(
        self,
        admin_client: ApiClient,
    ):
        events_resp = admin_client.get("/api/v1/admin/signing-key-events")
        events_resp.raise_for_status()
        events = events_resp.json()["items"]
        assert len(events) >= 1
        assert any(e["action"] in {"rotate", "revoke"} for e in events)

    def test_operation_request_list_available(self, admin_client: ApiClient):
        reqs_resp = admin_client.get("/api/v1/admin/signing-key-operation-requests")
        reqs_resp.raise_for_status()
        items = reqs_resp.json()["items"]
        assert isinstance(items, list)

    def test_approval_token_mismatch_fails(
        self,
        admin_client: ApiClient,
        admin2_client: ApiClient,
        admin_approval_token: str,
    ):
        create_resp = admin_client.post(
            "/api/v1/admin/signing-keys/rotate",
            json_body={
                "reason": "token mismatch test",
                "approval_token": admin_approval_token,
            },
        )
        create_resp.raise_for_status()
        request_id = create_resp.json()["request"]["id"]

        mismatch_resp = admin2_client.post(
            f"/api/v1/admin/signing-key-operation-requests/{request_id}/approve",
            json_body={"approval_token": "wrong-token"},
        )
        assert mismatch_resp.status_code == 403

    def test_cannot_revoke_last_trusted_key_without_emergency_replacement(
        self,
        admin_client: ApiClient,
        admin2_client: ApiClient,
        admin_approval_token: str,
    ):
        # Step 1: create exactly one active key for mock_hsm backend.
        rotate_resp = admin_client.post(
            "/api/v1/admin/signing-keys/rotate",
            json_body={
                "backend": "mock_hsm",
                "reason": "prepare single key revoke guard test",
                "approval_token": admin_approval_token,
            },
        )
        rotate_resp.raise_for_status()
        rotate_request_id = rotate_resp.json()["request"]["id"]

        approve_rotate = admin2_client.post(
            f"/api/v1/admin/signing-key-operation-requests/{rotate_request_id}/approve",
            json_body={"approval_token": admin_approval_token},
        )
        approve_rotate.raise_for_status()
        new_key_id = approve_rotate.json()["execution_result"]["new_key"]["key_id"]

        # Step 2: request revoke without emergency/replacement.
        revoke_resp = admin_client.post(
            f"/api/v1/admin/signing-keys/{new_key_id}/revoke",
            json_body={
                "reason": "should fail last-key guard",
                "approval_token": admin_approval_token,
                "emergency": False,
                "create_replacement": False,
            },
        )
        revoke_resp.raise_for_status()
        revoke_request_id = revoke_resp.json()["request"]["id"]

        approve_revoke = admin2_client.post(
            f"/api/v1/admin/signing-key-operation-requests/{revoke_request_id}/approve",
            json_body={"approval_token": admin_approval_token},
        )
        assert approve_revoke.status_code == 409

    def test_cannot_approve_executed_request_twice(
        self,
        admin_client: ApiClient,
        admin2_client: ApiClient,
        admin_approval_token: str,
    ):
        create_resp = admin_client.post(
            "/api/v1/admin/signing-keys/rotate",
            json_body={
                "reason": "double-approve test",
                "approval_token": admin_approval_token,
            },
        )
        create_resp.raise_for_status()
        request_id = create_resp.json()["request"]["id"]

        first_approve = admin2_client.post(
            f"/api/v1/admin/signing-key-operation-requests/{request_id}/approve",
            json_body={"approval_token": admin_approval_token},
        )
        first_approve.raise_for_status()

        second_approve = admin2_client.post(
            f"/api/v1/admin/signing-key-operation-requests/{request_id}/approve",
            json_body={"approval_token": admin_approval_token},
        )
        assert second_approve.status_code == 409
