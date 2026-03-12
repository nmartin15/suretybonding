import json
import os
from pathlib import Path

import jwt

BASE_URL = os.getenv("EBONDING_API_URL", "http://localhost:8000")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-32-byte-minimum-secret-key")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


def make_token(role: str, user_id: str) -> str:
    return jwt.encode({"sub": user_id, "role": role}, JWT_SECRET, algorithm=JWT_ALGORITHM)


ADMIN_TOKEN = os.getenv(
    "EBONDING_ADMIN_TOKEN",
    make_token("admin", "10000000-0000-0000-0000-000000000001"),
)
ADMIN2_TOKEN = os.getenv(
    "EBONDING_ADMIN2_TOKEN",
    make_token("admin", "10000000-0000-0000-0000-000000000004"),
)
BROKER_TOKEN = os.getenv(
    "EBONDING_BROKER_TOKEN",
    make_token("broker", "10000000-0000-0000-0000-000000000002"),
)
UNDERWRITER_TOKEN = os.getenv(
    "EBONDING_UNDERWRITER_TOKEN",
    make_token("underwriter", "10000000-0000-0000-0000-000000000003"),
)

# Timeouts aligned with PRD NFR Section 9.3
POLL_INTERVAL_SECONDS = 5
AUTO_ISSUE_TIMEOUT_SECONDS = int(os.getenv("AUTO_ISSUE_TIMEOUT", "600"))  # 10 min for tests
AUDIT_BUNDLE_TIMEOUT_SECONDS = 300  # 5 min per PRD success metric

# This file lives under tests/support/, so parent.parent.parent is repo root.
MANIFEST_SCHEMA_PATH = Path(__file__).parent.parent.parent / "manifest.schema.json"

# Pilot defaults — replace with actual pilot agency/carrier IDs
PILOT_OBLIGEE_ID = os.getenv("PILOT_OBLIGEE_ID", "00000000-0000-0000-0000-000000000001")
PILOT_CARRIER_ID = os.getenv("PILOT_CARRIER_ID", "00000000-0000-0000-0000-000000000002")

# Pre-approved clause IDs for T5 auto-issue testing
PRE_APPROVED_CLAUSE_IDS = json.loads(os.getenv("PRE_APPROVED_CLAUSE_IDS", "[]"))
ADMIN_APPROVAL_TOKEN = os.getenv("ADMIN_APPROVAL_TOKEN", "dev-approval-token")
