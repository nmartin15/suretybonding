# WA Performance Bond E-Bonding Platform

Court-defensible Washington State public-works performance bond issuance with HSM-signed manifests, notarization evidence, permissioned ledger proof, and litigation-ready audit bundles.

See [`SuretyBondingPRD.md`](./SuretyBondingPRD.md) for the full product requirements document.

---

## Repository Maturity State

This repository is currently in **handoff-to-build transition**:

- Product artifacts are present and detailed (`SuretyBondingPRD.md`, `openapi.yaml`, `manifest.schema.json`, acceptance tests).
- A full production implementation is **not** present yet (external adapters, HSM-backed signing, and ledger integrations remain mocked).
- The immediate goal is to keep docs/spec/tests/CI internally consistent and make the first executable vertical slice runnable.

---

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 16+ with [pgvector](https://github.com/pgvector/pgvector) extension (full stack target)
- Redis 7+ (full stack target)
- SoftHSM2 (full stack target) or AWS CloudHSM (staging/production)
- Node.js 20+ (optional, for OpenAPI client generation)

### 1. Clone and install

```bash
git clone <repo-url> && cd SuretyBonding
python -m venv .venv && source .venv/bin/activate
pip install -r dev-requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your local settings:
#   DATABASE_URL=postgresql+asyncpg://ebonding:password@localhost:5432/ebonding
#   REDIS_URL=redis://localhost:6379/0
#   HSM_MODE=softhsm
#   LEDGER_MODE=db_audit_log
#   RON_MODE=mock
#   KYC_MODE=mock
```

### 3. One-command preflight + migrations

```bash
python scripts/bootstrap_local.py
```

### 4. Start API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Generate local JWTs (dev)

```bash
python - <<'PY'
import jwt
secret = "dev-secret"
print("ADMIN:", jwt.encode({"sub":"10000000-0000-0000-0000-000000000001","role":"admin"}, secret, algorithm="HS256"))
print("BROKER:", jwt.encode({"sub":"10000000-0000-0000-0000-000000000002","role":"broker"}, secret, algorithm="HS256"))
print("UNDERWRITER:", jwt.encode({"sub":"10000000-0000-0000-0000-000000000003","role":"underwriter"}, secret, algorithm="HS256"))
PY
```

API docs available at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc`.

---

## Project Structure

```
SuretyBonding/
├── .github/workflows/
│   └── ci.yml                    # CI pipeline — lint/spec/tests
├── app/
│   ├── main.py                   # DB-backed API (bond lifecycle, manifest, audit bundle)
│   ├── auth.py                   # JWT auth + RBAC dependency guards
│   ├── db.py                     # SQLAlchemy async engine/session
│   ├── models.py                 # Core persistence models
│   └── schemas.py                # Request/response schemas
├── alembic/                      # Migration env + versions
├── alembic.ini                   # Alembic configuration
├── tests/
│   ├── conftest.py               # Shared fixtures
│   ├── support/                  # Shared test helpers and config
│   ├── unit/                     # Fast isolated unit tests
│   └── acceptance/
│       ├── manifest/             # T1
│       ├── notarization/         # T2
│       ├── ledger/               # T3
│       ├── litigation/           # T4
│       ├── policy/               # T5
│       └── security/             # T6
├── docs/
│   └── next-slice.md             # First executable vertical slice definition
├── manifest.schema.json          # Authoritative manifest JSON Schema
├── openapi.yaml                  # OpenAPI 3.1 spec
├── SuretyBondingPRD.md           # Product requirements document
├── requirements.txt              # Production dependencies
└── dev-requirements.txt          # Development + CI dependencies
```

---

## Running Tests

### Acceptance tests S0 + T1-T6

These tests currently validate contract behavior against the running API. Some tests require a real issued bond fixture and are intentionally skipped if required env vars are missing.

```bash
# Terminal 1: start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2: run acceptance tests
export EBONDING_API_URL=http://localhost:8000
export EBONDING_ADMIN_TOKEN=<your-admin-jwt>
export EBONDING_ADMIN2_TOKEN=<a-second-admin-jwt>
export EBONDING_BROKER_TOKEN=<your-broker-jwt>
export ISSUED_BOND_ID=<uuid-of-an-issued-bond>       # For T1/T2/T3
export PRE_APPROVED_CLAUSE_IDS='["uuid1","uuid2"]'    # For T5
export ADMIN_APPROVAL_TOKEN=<admin-approval-token>    # For T6

# Run individual tests
pytest tests/acceptance/smoke/test_s0_bootstrap_smoke.py -m acceptance -v --timeout=60
pytest tests/acceptance/manifest/test_t1_manifest_validation.py -m acceptance -v
pytest tests/acceptance/notarization/test_t2_notarization_evidence.py -m acceptance -v
pytest tests/acceptance/ledger/test_t3_ledger_proof.py -m acceptance -v
pytest tests/acceptance/litigation/test_t4_litigation_simulation.py -m acceptance -v --timeout=600
pytest tests/acceptance/policy/test_t5_auto_issue.py -m acceptance -v --timeout=900
pytest tests/acceptance/security/test_t6_signing_key_dual_control.py -m acceptance -v --timeout=180

# Run all acceptance tests
pytest tests/acceptance -m acceptance -v --timeout=900

# Run only fast unit tests
pytest tests/unit -m unit -v
```

### Full CI suite locally

```bash
# Lint
ruff check . && ruff format --check .
mypy --ignore-missing-imports .
bandit -r . -x ./tests --severity-level medium

# Validate specs
python -c "import json, jsonschema; jsonschema.Draft202012Validator.check_schema(json.load(open('manifest.schema.json')))"

# All tests
pytest tests/ -v --timeout=900 --cov=. --cov-report=term-missing

# Marker-targeted runs
pytest tests/ -m "not acceptance" -v --timeout=120
pytest tests/ -m acceptance -v --timeout=900
```

---

## Key Operations

### Issue a bond (API)

```bash
# 1. Create bond request
curl -X POST http://localhost:8000/api/v1/bonds \
  -H "Authorization: Bearer $BROKER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "principal_name": "Example Contractor LLC",
    "principal_ubi_number": "600000001",
    "contractor_registration_number": "EXMPL001",
    "obligee_agency_id": "'$PILOT_OBLIGEE_ID'",
    "contract_id": "CONTRACT-2026-001",
    "contract_amount": "500000.00",
    "penal_sum": "500000.00",
    "project_description": "Highway bridge rehabilitation",
    "project_county": "King"
  }'

# 2. Submit for evaluation
curl -X POST http://localhost:8000/api/v1/bonds/{bond_id}/submit \
  -H "Authorization: Bearer $BROKER_TOKEN"

# 3. Check status
curl http://localhost:8000/api/v1/bonds/{bond_id} \
  -H "Authorization: Bearer $BROKER_TOKEN"
```

### Produce an audit bundle

```bash
# Trigger generation (admin only)
curl -X POST http://localhost:8000/api/v1/audit-bundles/{manifest_id}/generate \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Download (once generated)
curl -o audit-bundle.zip \
  http://localhost:8000/api/v1/audit-bundles/{manifest_id} \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Verify a manifest

```bash
curl http://localhost:8000/api/v1/manifests/{manifest_id}/verify \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Signing key management (admin)

```bash
# List key history
curl http://localhost:8000/api/v1/admin/signing-keys \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# List immutable key audit events
curl http://localhost:8000/api/v1/admin/signing-key-events \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Create a rotate request (admin A)
curl -X POST http://localhost:8000/api/v1/admin/signing-keys/rotate \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"scheduled quarterly rotation","approval_token":"<admin-approval-token>"}'

# Create a revoke request (admin A)
curl -X POST http://localhost:8000/api/v1/admin/signing-keys/{key_id}/revoke \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"key compromise drill","approval_token":"<admin-approval-token>","emergency":true,"create_replacement":true}'

# List pending/previous operation requests
curl http://localhost:8000/api/v1/admin/signing-key-operation-requests \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Approve and execute request (must be different admin B)
curl -X POST http://localhost:8000/api/v1/admin/signing-key-operation-requests/{request_id}/approve \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"approval_token":"<admin-approval-token>"}'
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | — | PostgreSQL connection string |
| `JWT_SECRET` | `dev-secret-32-byte-minimum-secret-key` | JWT signing secret for API auth (use 32+ bytes) |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `SIGNING_BACKEND` | `db_pem` | Signing custody backend: `db_pem` (dev fallback) or `mock_hsm` (no private key persistence) |
| `ADMIN_APPROVAL_TOKEN` | `dev-approval-token` | Required dual-control token for key rotation/revocation actions |
| `APPROVAL_REPLAY_WINDOW_SECONDS` | `0` | Optional replay-defense window for approval token reuse across operation approvals |
| `EBONDING_API_URL` | `http://localhost:8000` | Base API URL used by tests |

---

## Deployment

### Staging

```bash
# Build and push container
docker build -t ebonding:latest .
docker push <registry>/ebonding:latest

# Deploy (assumes Kubernetes or ECS)
# Ensure the following are provisioned:
#   - PostgreSQL 16 with pgvector
#   - Redis 7
#   - SoftHSM or CloudHSM
#   - S3 buckets (audit bundles, RON recordings)
#   - Secrets in AWS Secrets Manager
```

### Production checklist

- [ ] CloudHSM cluster provisioned and initialized
- [ ] Permissioned ledger node operational
- [ ] RON provider API credentials configured
- [ ] KYC provider API credentials configured
- [ ] S3 buckets created with encryption and lifecycle policies
- [ ] SIEM integration configured
- [ ] JWT signing migrated from secret to HSM
- [ ] Acceptance tests T1–T5 passing against staging
- [ ] Legal counsel has signed off on manifest schema and legal memo template
- [ ] Pilot carrier and agency have signed Acceptance Attestation
- [ ] Key rotation and emergency revoke procedures tested
- [ ] Operational playbooks reviewed by on-call team

---

## Reference

- **PRD:** [`SuretyBondingPRD.md`](./SuretyBondingPRD.md)
- **Next Slice:** [`docs/next-slice.md`](./docs/next-slice.md)
- **Ops Runbook:** [`docs/ops-runbook.md`](./docs/ops-runbook.md)
- **Preflight Script:** [`scripts/preflight.py`](./scripts/preflight.py)
- **Bootstrap Script:** [`scripts/bootstrap_local.py`](./scripts/bootstrap_local.py)
- **Manifest Schema:** [`manifest.schema.json`](./manifest.schema.json)
- **OpenAPI Spec:** [`openapi.yaml`](./openapi.yaml) — view at `/docs` when server is running
- **Acceptance Tests:** [`tests/acceptance/`](./tests/acceptance/)
- **CI Pipeline:** [`.github/workflows/ci.yml`](./.github/workflows/ci.yml)
