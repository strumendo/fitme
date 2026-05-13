"""Write-side helpers for manual-input tables.

Pages don't run INSERT/UPDATE/DELETE inline — they call into this module so
mutation logic stays out of Streamlit code. Reads continue to live in
``queries.py``.

All timestamps are UTC ISO-8601 with second precision, matching the pattern
used by ``ingest.py``.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime, timezone

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# training_plan
# ---------------------------------------------------------------------------

def upsert_training_plan_slot(
    conn: sqlite3.Connection,
    *,
    effective_from: date,
    weekday: int,
    slot: int,
    activity_type: str,
    description: str | None = None,
    target_duration_min: int | None = None,
) -> int:
    """Insert or replace a plan slot for a given (effective_from, weekday, slot).

    The UNIQUE constraint makes this idempotent — re-saving the same slot in the
    same plan version updates the existing row. To supersede an entire plan,
    insert rows with a newer ``effective_from``.
    """
    cur = conn.execute(
        """
        INSERT INTO training_plan
            (effective_from, weekday, slot, activity_type, description,
             target_duration_min, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(effective_from, weekday, slot) DO UPDATE SET
            activity_type       = excluded.activity_type,
            description         = excluded.description,
            target_duration_min = excluded.target_duration_min
        """,
        (
            effective_from.isoformat(),
            weekday,
            slot,
            activity_type,
            description,
            target_duration_min,
            _now_iso(),
        ),
    )
    return cur.lastrowid or 0


def delete_training_plan_slot(conn: sqlite3.Connection, plan_id: int) -> None:
    conn.execute("DELETE FROM training_plan WHERE plan_id = ?", (plan_id,))


# ---------------------------------------------------------------------------
# training_log
# ---------------------------------------------------------------------------

def insert_training_log(
    conn: sqlite3.Connection,
    *,
    day: date,
    activity_type: str,
    duration_min: int | None = None,
    perceived_effort: int | None = None,
    notes: str | None = None,
    garmin_activity_id: int | None = None,
) -> int:
    now = _now_iso()
    cur = conn.execute(
        """
        INSERT INTO training_log
            (date, activity_type, duration_min, perceived_effort, notes,
             garmin_activity_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            day.isoformat(),
            activity_type,
            duration_min,
            perceived_effort,
            notes,
            garmin_activity_id,
            now,
            now,
        ),
    )
    return cur.lastrowid or 0


def update_training_log(
    conn: sqlite3.Connection,
    log_id: int,
    *,
    activity_type: str,
    duration_min: int | None = None,
    perceived_effort: int | None = None,
    notes: str | None = None,
    garmin_activity_id: int | None = None,
) -> None:
    conn.execute(
        """
        UPDATE training_log
        SET activity_type      = ?,
            duration_min       = ?,
            perceived_effort   = ?,
            notes              = ?,
            garmin_activity_id = ?,
            updated_at         = ?
        WHERE log_id = ?
        """,
        (
            activity_type,
            duration_min,
            perceived_effort,
            notes,
            garmin_activity_id,
            _now_iso(),
            log_id,
        ),
    )


def delete_training_log(conn: sqlite3.Connection, log_id: int) -> None:
    conn.execute("DELETE FROM training_log WHERE log_id = ?", (log_id,))


# ---------------------------------------------------------------------------
# food_log
# ---------------------------------------------------------------------------

def insert_food_log(
    conn: sqlite3.Connection,
    *,
    day: date,
    description: str,
    meal: str | None = None,
    kcal: float | None = None,
    protein_g: float | None = None,
    carbs_g: float | None = None,
    fat_g: float | None = None,
    notes: str | None = None,
) -> int:
    now = _now_iso()
    cur = conn.execute(
        """
        INSERT INTO food_log
            (date, meal, description, kcal, protein_g, carbs_g, fat_g, notes,
             created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            day.isoformat(),
            meal,
            description,
            kcal,
            protein_g,
            carbs_g,
            fat_g,
            notes,
            now,
            now,
        ),
    )
    return cur.lastrowid or 0


def update_food_log(
    conn: sqlite3.Connection,
    food_id: int,
    *,
    description: str,
    meal: str | None = None,
    kcal: float | None = None,
    protein_g: float | None = None,
    carbs_g: float | None = None,
    fat_g: float | None = None,
    notes: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE food_log
        SET meal        = ?,
            description = ?,
            kcal        = ?,
            protein_g   = ?,
            carbs_g     = ?,
            fat_g       = ?,
            notes       = ?,
            updated_at  = ?
        WHERE food_id = ?
        """,
        (
            meal,
            description,
            kcal,
            protein_g,
            carbs_g,
            fat_g,
            notes,
            _now_iso(),
            food_id,
        ),
    )


def delete_food_log(conn: sqlite3.Connection, food_id: int) -> None:
    conn.execute("DELETE FROM food_log WHERE food_id = ?", (food_id,))
