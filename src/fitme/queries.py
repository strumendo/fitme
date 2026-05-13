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


def plan_for_date(conn: sqlite3.Connection, day: date) -> list[dict]:
    """Return the training plan rows in effect on ``day``, ordered by slot.

    The "effective" plan is the set of rows whose ``effective_from`` matches
    the latest version with ``effective_from <= day``. Older versions stay in
    the table so history remains reproducible.
    """
    row = conn.execute(
        "SELECT MAX(effective_from) AS ef FROM training_plan "
        "WHERE effective_from <= ?",
        (day.isoformat(),),
    ).fetchone()
    effective_from = row["ef"] if row else None
    if not effective_from:
        return []
    rows = conn.execute(
        "SELECT * FROM training_plan WHERE effective_from = ? "
        "ORDER BY weekday, slot",
        (effective_from,),
    ).fetchall()
    return [dict(r) for r in rows]


def training_plan_versions(conn: sqlite3.Connection) -> list[str]:
    """Distinct ``effective_from`` dates, newest first."""
    rows = conn.execute(
        "SELECT DISTINCT effective_from FROM training_plan "
        "ORDER BY effective_from DESC"
    ).fetchall()
    return [r["effective_from"] for r in rows]


def training_log_range(
    conn: sqlite3.Connection, start: date, end: date
) -> list[dict]:
    """Return training log rows in ``[start, end]``, newest first."""
    rows = conn.execute(
        "SELECT * FROM training_log WHERE date BETWEEN ? AND ? "
        "ORDER BY date DESC, log_id DESC",
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    return [dict(r) for r in rows]


def food_log_range(
    conn: sqlite3.Connection, start: date, end: date
) -> list[dict]:
    """Return food log rows in ``[start, end]``, newest first."""
    rows = conn.execute(
        "SELECT * FROM food_log WHERE date BETWEEN ? AND ? "
        "ORDER BY date DESC, food_id DESC",
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    return [dict(r) for r in rows]


def food_macros_summary(
    conn: sqlite3.Connection, start: date, end: date
) -> list[dict]:
    """Per-day totals of kcal + macros over ``[start, end]``.

    Days with no food entries are omitted (the UI fills the gap as needed).
    """
    rows = conn.execute(
        """
        SELECT date,
               SUM(kcal)      AS kcal,
               SUM(protein_g) AS protein_g,
               SUM(carbs_g)   AS carbs_g,
               SUM(fat_g)     AS fat_g,
               COUNT(*)       AS entries
        FROM food_log
        WHERE date BETWEEN ? AND ?
        GROUP BY date
        ORDER BY date
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    return [dict(r) for r in rows]
