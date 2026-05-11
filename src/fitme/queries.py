"""Read-side helpers over the fitme SQLite tables.

Each helper returns a plain ``dict`` (or ``None`` when the row is missing).
This module deliberately stays free of pandas — range/DataFrame helpers will
be added in Phase 2 so the DB layer can be exercised without pandas in the
loop.
"""
from __future__ import annotations

import sqlite3
from datetime import date


def _one(conn: sqlite3.Connection, table: str, day: date) -> dict | None:
    row = conn.execute(
        f"SELECT * FROM {table} WHERE date = ?", (day.isoformat(),)  # noqa: S608 — table name is a code constant
    ).fetchone()
    return dict(row) if row else None


def get_daily_summary(conn: sqlite3.Connection, day: date) -> dict | None:
    return _one(conn, "daily_summary", day)


def get_heart_rate(conn: sqlite3.Connection, day: date) -> dict | None:
    return _one(conn, "heart_rate", day)


def get_sleep(conn: sqlite3.Connection, day: date) -> dict | None:
    return _one(conn, "sleep", day)


def get_weight(conn: sqlite3.Connection, day: date) -> dict | None:
    return _one(conn, "weight", day)


def _range(
    conn: sqlite3.Connection, table: str, start: date, end: date
) -> list[dict]:
    rows = conn.execute(
        f"SELECT * FROM {table} WHERE date BETWEEN ? AND ? ORDER BY date",  # noqa: S608 — table name is a code constant
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    return [dict(r) for r in rows]


def daily_summary_range(
    conn: sqlite3.Connection, start: date, end: date
) -> list[dict]:
    return _range(conn, "daily_summary", start, end)


def heart_rate_range(
    conn: sqlite3.Connection, start: date, end: date
) -> list[dict]:
    return _range(conn, "heart_rate", start, end)


def sleep_range(conn: sqlite3.Connection, start: date, end: date) -> list[dict]:
    return _range(conn, "sleep", start, end)


def weight_range(conn: sqlite3.Connection, start: date, end: date) -> list[dict]:
    return _range(conn, "weight", start, end)
