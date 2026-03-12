# Acceptance Test Guide

This folder contains end-to-end acceptance tests (`T1`-`T6`) that validate externally visible platform behavior against a running API.

## Purpose

- Keep compliance-critical acceptance tests organized by domain.
- Prevent test coupling and helper duplication.
- Make CI targeting and local test execution predictable.

## Folder Layout

- `manifest/` — manifest validity and signature checks (`T1`)
- `notarization/` — notarization metadata and evidence checks (`T2`)
- `ledger/` — ledger anchoring and hash checks (`T3`)
- `litigation/` — audit bundle/subpoena drill checks (`T4`)
- `policy/` — auto-issue policy gate checks (`T5`)
- `security/` — signing-key dual-control workflow checks (`T6`)

## Conventions

- All tests in this tree must be marked `@pytest.mark.acceptance`.
- Test filenames follow `test_t<n>_<topic>.py` for traceability to acceptance criteria.
- Prefer shared fixtures from `tests/conftest.py` and shared helpers from `tests/support/`.
- Do not import helpers from other test modules; extract shared logic to `tests/support/`.
- Keep tests scenario-focused and assertion-rich; avoid embedding non-essential setup logic.

## Running

```bash
# All acceptance tests
pytest tests/acceptance -m acceptance -v --timeout=900

# Single domain
pytest tests/acceptance/manifest -m acceptance -v
```
