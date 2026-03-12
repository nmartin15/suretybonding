from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from urllib.parse import urlsplit

import asyncpg
from dotenv import load_dotenv


REQUIRED_VARS = [
    "DATABASE_URL",
    "JWT_SECRET",
    "ADMIN_APPROVAL_TOKEN",
    "SIGNING_BACKEND",
]
ALLOWED_BACKENDS = {"db_pem", "mock_hsm"}


def _normalize_asyncpg_url(url: str) -> str:
    # SQLAlchemy async URL -> asyncpg URL
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url[len("postgresql+asyncpg://") :]
    return url


def _check_env() -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_VARS:
        if not os.getenv(key):
            errors.append(f"Missing required env var: {key}")

    jwt_secret = os.getenv("JWT_SECRET", "")
    if jwt_secret and len(jwt_secret) < 32:
        errors.append("JWT_SECRET must be at least 32 characters")

    backend = os.getenv("SIGNING_BACKEND", "")
    if backend and backend not in ALLOWED_BACKENDS:
        errors.append(f"SIGNING_BACKEND must be one of {sorted(ALLOWED_BACKENDS)}")

    database_url = os.getenv("DATABASE_URL", "")
    if database_url:
        parsed = urlsplit(database_url)
        if not parsed.scheme or not parsed.hostname:
            errors.append("DATABASE_URL is not a valid URL")
    return errors


async def _check_db() -> str | None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return "DATABASE_URL is not set"
    try:
        conn = await asyncpg.connect(_normalize_asyncpg_url(database_url))
        try:
            await conn.execute("SELECT 1")
        finally:
            await conn.close()
        return None
    except Exception as exc:  # pragma: no cover
        return f"Database connectivity failed: {exc}"


def _check_alembic_available() -> str | None:
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
        return None
    except Exception as exc:  # pragma: no cover
        return f"Alembic is not available: {exc}"


def main() -> int:
    load_dotenv()
    print("[preflight] Starting local preflight checks...")

    errors = _check_env()
    alembic_err = _check_alembic_available()
    if alembic_err:
        errors.append(alembic_err)

    db_err = asyncio.run(_check_db())
    if db_err:
        errors.append(db_err)

    if errors:
        print("[preflight] FAILED")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("[preflight] OK")
    print("  - Environment variables: valid")
    print("  - Alembic: available")
    print("  - Database connectivity: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
