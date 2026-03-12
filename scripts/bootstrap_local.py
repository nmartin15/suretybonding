from __future__ import annotations

import subprocess
import sys


def _run(cmd: list[str], label: str) -> None:
    print(f"[bootstrap] {label}...")
    subprocess.run(cmd, check=True)


def main() -> int:
    _run([sys.executable, "scripts/preflight.py"], "Running preflight")
    _run([sys.executable, "-m", "alembic", "upgrade", "head"], "Applying migrations")
    print("[bootstrap] OK")
    print("[bootstrap] Next: start API with:")
    print("  uvicorn app.main:app --host 0.0.0.0 --port 8000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
