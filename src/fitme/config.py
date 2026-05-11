"""Environment configuration loaded from .env at the project root."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    garmin_email: str | None
    garmin_password: str | None
    garmin_tokens_path: Path


def load() -> Settings:
    tokens = os.getenv("GARMINTOKENS", "~/.garminconnect")
    return Settings(
        garmin_email=os.getenv("GARMIN_EMAIL"),
        garmin_password=os.getenv("GARMIN_PASSWORD"),
        garmin_tokens_path=Path(tokens).expanduser(),
    )
