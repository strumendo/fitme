"""Nutrition coach — turn the DB into daily kcal + macro targets.

Mirrors ``coach.py``, split so the data half is testable without the
network:

- :func:`build_context` assembles a deterministic summary of the goal,
  bodyweight trend, Garmin energy expenditure, recent intake, and training
  load. Pure reads via ``queries.*`` — no pandas, no network (PR 1).
- ``generate_targets`` (PR 2) will send that summary to Claude and return a
  structured ``{kcal, protein_g, carbs_g, fat_g, rationale, adjustment}``.

The active target lives in the ``nutrition_target`` table (see
``repository.insert_nutrition_target`` / ``queries.active_nutrition_target``).
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import date, timedelta

from fitme import queries

logger = logging.getLogger(__name__)

EXPENDITURE_LOOKBACK_DAYS = 14
INTAKE_LOOKBACK_DAYS = 14
WEIGHT_TREND_DAYS = 28
TRAINING_LOOKBACK_DAYS = 28


def build_context(
    conn: sqlite3.Connection,
    goal: dict | None,
    *,
    today: date | None = None,
) -> dict:
    """Assemble the data summary the nutrition coach reasons over.

    ``goal`` is an ``active_goal`` row (or ``None``). ``today`` defaults to
    ``date.today()`` and is injectable for deterministic tests. Returns a
    JSON-serializable dict; no network, no pandas.
    """
    today = today or date.today()
    exp_start = today - timedelta(days=EXPENDITURE_LOOKBACK_DAYS - 1)
    intake_start = today - timedelta(days=INTAKE_LOOKBACK_DAYS - 1)
    weight_start = today - timedelta(days=WEIGHT_TREND_DAYS - 1)
    train_start = today - timedelta(days=TRAINING_LOOKBACK_DAYS - 1)

    type_mix = queries.training_type_mix(conn, train_start, today)
    total_sessions = sum(r["sessions"] for r in type_mix)
    weeks = TRAINING_LOOKBACK_DAYS / 7.0

    return {
        "goal": _goal_summary(goal),
        "today": today.isoformat(),
        "bodyweight": _bodyweight_trend(conn, weight_start, today),
        "expenditure": {
            "avg_daily_kcal": queries.avg_daily_expenditure(
                conn, exp_start, today
            ),
            "window_days": EXPENDITURE_LOOKBACK_DAYS,
        },
        "intake": {
            **queries.intake_averages(conn, intake_start, today),
            "window_days": INTAKE_LOOKBACK_DAYS,
        },
        "training": {
            "lookback_days": TRAINING_LOOKBACK_DAYS,
            "sessions_per_week": round(total_sessions / weeks, 1),
            "type_mix": type_mix,
        },
    }


def _goal_summary(goal: dict | None) -> dict | None:
    if not goal:
        return None
    return {
        "preset": goal["goal_preset"],
        "days_per_week": goal["days_per_week"],
        "session_length_min": goal["session_length_min"],
    }


def _bodyweight_trend(
    conn: sqlite3.Connection, start: date, end: date
) -> dict | None:
    """Latest bodyweight + change and weekly rate over the window.

    The rate is the signal the adjustment loop leans on: a goal that wants
    weight to move but a flat trend means the calorie target needs changing.
    """
    rows = [
        w for w in queries.weight_range(conn, start, end)
        if w["weight_kg"] is not None
    ]
    if not rows:
        return None
    first, latest = rows[0], rows[-1]
    span_days = (
        date.fromisoformat(latest["date"]) - date.fromisoformat(first["date"])
    ).days
    delta = round(latest["weight_kg"] - first["weight_kg"], 1)
    rate = (
        round(delta / (span_days / 7.0), 2) if span_days >= 1 else None
    )
    return {
        "latest_kg": latest["weight_kg"],
        "as_of": latest["date"],
        "window_days": WEIGHT_TREND_DAYS,
        "delta_kg": delta,
        "rate_kg_per_week": rate,
    }
