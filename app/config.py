from __future__ import annotations

import os


class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://ebonding:password@localhost:5432/ebonding",
    )
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    signing_backend: str = os.getenv("SIGNING_BACKEND", "db_pem")
    admin_approval_token: str = os.getenv("ADMIN_APPROVAL_TOKEN", "dev-approval-token")
    approval_replay_window_seconds: int = int(os.getenv("APPROVAL_REPLAY_WINDOW_SECONDS", "0"))


settings = Settings()
