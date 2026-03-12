# First Executable Vertical Slice

## Goal

Move from documentation-only handoff artifacts to a runnable contract-first baseline that can be exercised locally and in CI.

## Slice Scope (Now Implemented)

- Minimal FastAPI app scaffold in `app/main.py`
- Health endpoint: `GET /api/v1/health`
- Manifest stub endpoints:
  - `GET /api/v1/manifests/{manifest_id}`
  - `GET /api/v1/manifests/{manifest_id}/verify`
- Bond evidence endpoint used by T1:
  - `GET /api/v1/bonds/{bond_id}/pdf`

## What This Unlocks

- `uvicorn app.main:app --reload` runs immediately with no additional code generation.
- OpenAPI and acceptance tests now target realistic, discoverable endpoint contracts.
- Team can incrementally replace in-memory sample responses with database + adapter-backed implementations.

## Next Build Steps

1. Replace hard-coded sample manifest/bond with persistence-backed models.
2. Implement authentication and role enforcement from PRD Section 12.
3. Add bond lifecycle endpoints (`POST /bonds`, `POST /bonds/{id}/submit`) with state transitions.
4. Implement audit bundle generation contract (`POST/GET /audit-bundles/{manifest_id}`).
5. Turn verify endpoint checks from stubs into real cryptographic and ledger checks.
