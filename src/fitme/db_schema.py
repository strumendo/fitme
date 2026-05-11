"""SQLite schema and forward migrations for the fitme DB.

Migrations are hand-written Python callables keyed by target version. On every
``db.connect()`` we read ``schema_version``, compare to ``SCHEMA_VERSION``, and
apply any missing forward migrations. No down-migrations.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Callable

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


def _current_version(conn: sqlite3.Connection) -> int:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    return int(row[0]) if row else 0


def _set_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))


def _migrate_v1(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE daily_summary (
            date            TEXT PRIMARY KEY,
            steps           INTEGER,
            distance_m      REAL,
            calories_kcal   REAL,
            active_minutes  INTEGER,
            floors_climbed  INTEGER,
            raw_json        TEXT,
            fetched_at      TEXT NOT NULL
        );

        CREATE TABLE heart_rate (
            date            TEXT PRIMARY KEY,
            resting_bpm     INTEGER,
            max_bpm         INTEGER,
            min_bpm         INTEGER,
            avg_bpm         INTEGER,
            raw_json        TEXT,
            fetched_at      TEXT NOT NULL
        );

        CREATE TABLE sleep (
            date            TEXT PRIMARY KEY,
            total_seconds   INTEGER,
            deep_seconds    INTEGER,
            light_seconds   INTEGER,
            rem_seconds     INTEGER,
            awake_seconds   INTEGER,
            raw_json        TEXT,
            fetched_at      TEXT NOT NULL
        );

        CREATE TABLE weight (
            date            TEXT PRIMARY KEY,
            weight_kg       REAL,
            body_fat_pct    REAL,
            body_water_pct  REAL,
            muscle_mass_kg  REAL,
            bone_mass_kg    REAL,
            raw_json        TEXT,
            fetched_at      TEXT NOT NULL
        );
        """
    )


_MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {
    1: _migrate_v1,
}


def migrate(conn: sqlite3.Connection) -> None:
    """Bring ``conn`` up to ``SCHEMA_VERSION`` by applying missing migrations."""
    current = _current_version(conn)
    if current >= SCHEMA_VERSION:
        return
    for version in range(current + 1, SCHEMA_VERSION + 1):
        logger.info("Applying schema migration v%d", version)
        _MIGRATIONS[version](conn)
        _set_version(conn, version)
    conn.commit()
