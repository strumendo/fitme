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


def get_body_battery(conn: sqlite3.Connection, day: date) -> dict | None:
    return _one(conn, "body_battery", day)


def get_stress(conn: sqlite3.Connection, day: date) -> dict | None:
    return _one(conn, "stress", day)


def get_hrv(conn: sqlite3.Connection, day: date) -> dict | None:
    return _one(conn, "hrv", day)


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


def body_battery_range(
    conn: sqlite3.Connection, start: date, end: date
) -> list[dict]:
    return _range(conn, "body_battery", start, end)


def stress_range(conn: sqlite3.Connection, start: date, end: date) -> list[dict]:
    return _range(conn, "stress", start, end)


def hrv_range(conn: sqlite3.Connection, start: date, end: date) -> list[dict]:
    return _range(conn, "hrv", start, end)


def activities_range(
    conn: sqlite3.Connection,
    start: date,
    end: date,
    activity_type: str | None = None,
) -> list[dict]:
    """Return activities with start date in ``[start, end]``, newest first.

    Optionally filtered by Garmin ``typeKey`` (e.g. ``running``, ``cycling``).
    """
    sql = (
        "SELECT * FROM activities WHERE date BETWEEN ? AND ?"
    )
    params: list[object] = [start.isoformat(), end.isoformat()]
    if activity_type:
        sql += " AND type = ?"
        params.append(activity_type)
    sql += " ORDER BY start_time DESC"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def activity_types(
    conn: sqlite3.Connection, start: date, end: date
) -> list[str]:
    """Distinct activity types in ``[start, end]``, sorted."""
    rows = conn.execute(
        "SELECT DISTINCT type FROM activities "
        "WHERE date BETWEEN ? AND ? AND type IS NOT NULL "
        "ORDER BY type",
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    return [r["type"] for r in rows]
