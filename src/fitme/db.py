"""SQLite connection helpers for the fitme DB.

The single public entry point is ``connect()`` — a context manager that opens
the configured DB (creating the parent directory on first use), applies any
pending migrations, yields the connection, and commits on clean exit.
"""
from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from fitme.config import Settings, load
from fitme.db_schema import migrate

logger = logging.getLogger(__name__)


def _resolve_path(settings: Settings | None) -> Path:
    return (settings or load()).db_path


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Open the fitme DB, run forward migrations, yield the connection.

    Commits on clean exit; rolls back if the body raises. The parent directory
    is created on demand so ``data/fitme.db`` works out of the box.
    """
    db_path = path or _resolve_path(None)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        migrate(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
