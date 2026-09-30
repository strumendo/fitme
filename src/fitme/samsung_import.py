"""Import a Samsung Health payload file exported by the companion app.

File fallback for when the phone can't reach ``fitme.receiver`` — same JSON,
same ``samsung.ingest_payload``.

CLI::

    uv run python -m fitme.samsung_import ~/Downloads/samsung-health.json
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from fitme import samsung
from fitme.db import connect
from fitme.logging_config import setup as setup_logging

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    parser = argparse.ArgumentParser(
        prog="fitme.samsung_import",
        description="Import a Samsung Health JSON payload into the local fitme DB.",
    )
    parser.add_argument("file", type=Path, help="payload JSON exported by the app")
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.file.expanduser().read_text(encoding="utf-8"))
    except OSError as err:
        logger.error("could not read %s: %s", args.file, err)
        return 2
    except ValueError as err:
        logger.error("%s is not valid JSON: %s", args.file, err)
        return 2

    try:
        with connect() as conn:
            counts = samsung.ingest_payload(conn, payload)
    except samsung.PayloadError as err:
        logger.error("invalid payload: %s", err)
        return 2

    logger.info("done. %d rows written: %s", sum(counts.values()), counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
