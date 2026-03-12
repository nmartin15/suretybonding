# Signing Key Operations Runbook

## Preconditions

- Database is reachable and migrations are applied:
  - `python -m alembic upgrade head`
- API is running:
  - `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Two distinct admin JWTs exist (`ADMIN_A`, `ADMIN_B`), each with role `admin`.
- Shared approval token is configured in environment (`ADMIN_APPROVAL_TOKEN`).

## 1) Routine key rotation (dual control)

### Step A — Request (Admin A)

```bash
curl -X POST http://localhost:8000/api/v1/admin/signing-keys/rotate \
  -H "Authorization: Bearer $ADMIN_A" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "scheduled rotation",
    "approval_token": "<admin-approval-token>"
  }'
```

Capture `request.id`.

### Step B — Approve/execute (Admin B)

```bash
curl -X POST http://localhost:8000/api/v1/admin/signing-key-operation-requests/{request_id}/approve \
  -H "Authorization: Bearer $ADMIN_B" \
  -H "Content-Type: application/json" \
  -d '{
    "approval_token": "<admin-approval-token>"
  }'
```

Expected: request status `executed` and `execution_result.status = rotated`.

## 2) Key revoke (non-emergency)

### Step A — Request revoke (Admin A)

```bash
curl -X POST http://localhost:8000/api/v1/admin/signing-keys/{key_id}/revoke \
  -H "Authorization: Bearer $ADMIN_A" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "planned decommission",
    "approval_token": "<admin-approval-token>",
    "emergency": false,
    "create_replacement": true
  }'
```

### Step B — Approve/execute (Admin B)

```bash
curl -X POST http://localhost:8000/api/v1/admin/signing-key-operation-requests/{request_id}/approve \
  -H "Authorization: Bearer $ADMIN_B" \
  -H "Content-Type: application/json" \
  -d '{
    "approval_token": "<admin-approval-token>"
  }'
```

## 3) Emergency revoke (last-key safe path)

If target key is the last trusted active key, request must include:

- `emergency: true`
- `create_replacement: true`

Otherwise approval fails with `409`.

## 4) Verification / evidence

- List keys:
  - `GET /api/v1/admin/signing-keys`
- List operation requests:
  - `GET /api/v1/admin/signing-key-operation-requests`
- List immutable events:
  - `GET /api/v1/admin/signing-key-events`

Confirm:

- operation request has requester and different approver
- request status is `executed`
- key event exists with action `rotate` or `revoke`

## 5) Failure recovery

- **Requester tries to approve own request**: expect `409`; use different admin.
- **Approval token mismatch**: expect `403`; verify token source and retry.
- **Replay window rejection** (`409`): wait until replay window expires or use alternate approval mechanism.
- **No active signing key** (`503` during issuance): create/approve a rotate request for active backend.
