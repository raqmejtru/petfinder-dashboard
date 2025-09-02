# backend/app/config.py
from __future__ import annotations
from pydantic import BaseModel

import os
from typing import Final
from dotenv import load_dotenv

# Load .env for local dev (no-op if not present)
load_dotenv()


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Set it in your environment or .env file."
        )
    return value


class Settings(BaseModel):
    # Database URL defaults to SQLite if not set
    database_url: Final[str] = os.getenv("DATABASE_URL", "sqlite:///./local.db")

    # Required secrets
    pf_client_id: Final[str] = _require_env("PF_CLIENT_ID")
    pf_client_secret: Final[str] = _require_env("PF_CLIENT_SECRET")


settings = Settings()
