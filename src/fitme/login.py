"""One-off interactive login that handles MFA and caches OAuth tokens.

Run with:
    uv run python -m fitme.login

After it succeeds, the dashboard (and any other entry point) can rely on the
cached tokens at ``$GARMINTOKENS`` (default ``~/.garminconnect``) without
re-prompting until the refresh token expires.
"""
from __future__ import annotations

import logging
from getpass import getpass

from garminconnect import Garmin, GarminConnectAuthenticationError

from fitme.config import load
from fitme.logging_config import setup as setup_logging

logger = logging.getLogger(__name__)


def main() -> int:
    setup_logging()
    settings = load()
    tokens_path = str(settings.garmin_tokens_path)

    email = settings.garmin_email or input("Garmin email: ").strip()
    password = settings.garmin_password or getpass("Garmin password: ")

    try:
        client = Garmin(
            email=email,
            password=password,
            prompt_mfa=lambda: input("MFA code: ").strip(),
        )
        client.login(tokens_path)
    except GarminConnectAuthenticationError as err:
        logger.error("Authentication failed: %s", err)
        return 1

    logger.info("Login OK. Tokens cached at %s", tokens_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
