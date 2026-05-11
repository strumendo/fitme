"""Garmin Connect client wrapper.

Handles login with cached OAuth tokens (no re-auth on every run) and exposes
small helpers for the data the dashboard consumes.
"""
from __future__ import annotations

from datetime import date

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
)

from fitme.config import Settings, load


class GarminAuthError(RuntimeError):
    """Raised when no cached tokens exist and no credentials are configured."""


def get_client(settings: Settings | None = None) -> Garmin:
    """Return a logged-in Garmin client, restoring cached tokens when possible.

    First tries the token store at ``settings.garmin_tokens_path``.
    Falls back to email/password from .env. If neither works, raises
    ``GarminAuthError`` so the caller can prompt for an interactive login
    (which Streamlit cannot do — see scripts/login.py).
    """
    settings = settings or load()
    tokens_path = str(settings.garmin_tokens_path)

    try:
        client = Garmin()
        client.login(tokens_path)
        return client
    except (GarminConnectAuthenticationError, GarminConnectConnectionError):
        pass

    if not (settings.garmin_email and settings.garmin_password):
        raise GarminAuthError(
            "No valid Garmin tokens at "
            f"{tokens_path} and GARMIN_EMAIL/GARMIN_PASSWORD not set in .env. "
            "Run `uv run python -m fitme.login` once to authenticate (handles MFA)."
        )

    client = Garmin(email=settings.garmin_email, password=settings.garmin_password)
    client.login(tokens_path)
    return client


def daily_summary(client: Garmin, day: date | None = None) -> dict:
    return client.get_user_summary((day or date.today()).isoformat())


def heart_rate(client: Garmin, day: date | None = None) -> dict:
    return client.get_heart_rates((day or date.today()).isoformat())


def sleep(client: Garmin, day: date | None = None) -> dict:
    return client.get_sleep_data((day or date.today()).isoformat())


def body_composition(client: Garmin, day: date | None = None) -> dict:
    """Return body composition for ``day``.

    Garmin's response is ``{"totalAverage": {...}, "dateWeightList": [...]}``.
    Callers typically read ``totalAverage`` for the per-day aggregate.
    """
    iso = (day or date.today()).isoformat()
    return client.get_body_composition(iso)
