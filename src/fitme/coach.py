"""Training coach — turn the DB into a recommended weekly program.

Two responsibilities, split so the data half is testable without the network:

- :func:`build_context` assembles a deterministic summary of the goal,
  training history, layoff, bodyweight trend, and Garmin recovery signals.
  Pure reads via ``queries.*`` — no pandas, no network (PR 1).
- ``generate_program`` (PR 2) will send that summary to Claude and return a
  structured weekly program.

The goal presets the user can pick from. The active goal lives in the
``training_goal`` table (see ``repository.insert_training_goal`` /
``queries.active_goal``).
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import date, timedelta

from fitme import queries

logger = logging.getLogger(__name__)

#: Fixed goal presets. The label is what the user picks; it's stored verbatim
#: in ``training_goal.goal_preset`` and passed to the coach.
GOAL_PRESETS: tuple[str, ...] = (
    "hypertrophy",
    "strength",
    "fat_loss",
    "maintenance",
    "endurance",
)

HISTORY_LOOKBACK_DAYS = 90
RECOVERY_LOOKBACK_DAYS = 14


def build_context(
    conn: sqlite3.Connection,
    goal: dict | None,
    *,
    today: date | None = None,
) -> dict:
    """Assemble the data summary the coach reasons over.

    ``goal`` is an ``active_goal`` row (or ``None``). ``today`` defaults to
    ``date.today()`` and is injectable so the summary is deterministic in
    tests. Returns a JSON-serializable dict; no network, no pandas.
    """
    today = today or date.today()
    start = today - timedelta(days=HISTORY_LOOKBACK_DAYS - 1)
    recovery_start = today - timedelta(days=RECOVERY_LOOKBACK_DAYS - 1)

    type_mix = queries.training_type_mix(conn, start, today)
    total_sessions = sum(r["sessions"] for r in type_mix)
    weeks = HISTORY_LOOKBACK_DAYS / 7.0

    return {
        "goal": _goal_summary(goal),
        "today": today.isoformat(),
        "layoff_days": queries.days_since_last_session(conn, today),
        "history": {
            "lookback_days": HISTORY_LOOKBACK_DAYS,
            "total_sessions": total_sessions,
            "sessions_per_week": round(total_sessions / weeks, 1),
            "type_mix": type_mix,
            "exercises": _exercise_progression(conn, start, today),
        },
        "bodyweight": _bodyweight_trend(conn, start, today),
        "recovery": queries.recovery_averages(conn, recovery_start, today),
    }


def _goal_summary(goal: dict | None) -> dict | None:
    if not goal:
        return None
    return {
        "preset": goal["goal_preset"],
        "days_per_week": goal["days_per_week"],
        "session_length_min": goal["session_length_min"],
    }


def _exercise_progression(
    conn: sqlite3.Connection, start: date, end: date
) -> list[dict]:
    """Per-exercise latest working load + change over the window.

    Only loaded sets (weight and reps both present) count toward progression;
    bodyweight-only movements are skipped, consistent with the Strength page.
    """
    out: list[dict] = []
    for name in queries.exercise_names(conn, start, end):
        history = queries.exercise_history(conn, name, start, end)
        loaded = [
            s for s in history
            if s["weight_kg"] is not None and s["reps"] is not None
        ]
        if not loaded:
            continue
        first, last = loaded[0], loaded[-1]
        out.append(
            {
                "name": name,
                "sessions": len({s["date"] for s in history}),
                "latest_weight_kg": last["weight_kg"],
                "latest_reps": last["reps"],
                "weight_delta_kg": round(
                    last["weight_kg"] - first["weight_kg"], 1
                ),
            }
        )
    return out


def _bodyweight_trend(
    conn: sqlite3.Connection, start: date, end: date
) -> dict | None:
    rows = [
        w for w in queries.weight_range(conn, start, end)
        if w["weight_kg"] is not None
    ]
    if not rows:
        return None
    latest = rows[-1]
    return {
        "latest_kg": latest["weight_kg"],
        "as_of": latest["date"],
        "delta_over_window_kg": round(
            latest["weight_kg"] - rows[0]["weight_kg"], 1
        ),
    }
