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

import json
import logging
import sqlite3
from datetime import date, timedelta

from fitme import config, queries

logger = logging.getLogger(__name__)


class CoachError(RuntimeError):
    """Program generation failed (missing key, API error, bad response).

    Carries a user-facing message the Coach page can show via ``st.error``.
    """

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

MODEL = "claude-opus-4-8"

#: JSON schema the model's weekly program must conform to. Kept strict
#: (``additionalProperties: false``, all properties required) for
#: ``output_config.format``. ``reps`` is a string so it can carry ranges or
#: "AMRAP"; rest/cardio days use an empty ``exercises`` list and put the work
#: in ``description``. ``target_duration_min`` is 0 for rest days.
PROGRAM_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "rationale": {"type": "string"},
        "week": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "weekday": {"type": "integer", "enum": [0, 1, 2, 3, 4, 5, 6]},
                    "focus": {"type": "string"},
                    "description": {"type": "string"},
                    "target_duration_min": {"type": "integer"},
                    "exercises": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "sets": {"type": "integer"},
                                "reps": {"type": "string"},
                                "suggested_load": {"type": "string"},
                            },
                            "required": ["name", "sets", "reps", "suggested_load"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": [
                    "weekday", "focus", "description",
                    "target_duration_min", "exercises",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["rationale", "week"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """\
You are a strength & conditioning coach building one week of training for a \
single athlete. You receive a JSON summary of their goal, recent training \
history (90 days, with per-exercise load progression), days since their last \
session (layoff), bodyweight trend, and Garmin recovery averages (last 14 \
days). Produce a 7-day program.

Principles:
- Respect the goal preset (hypertrophy / strength / fat_loss / maintenance / \
endurance), the available days per week, and the target session length. Fill \
the remaining days with rest or light activity.
- After a long layoff (roughly a week or more), ramp volume and load back up \
rather than resuming at the athlete's previous peak.
- When recovery signals are poor (low sleep, low body battery, low HRV, high \
stress), reduce total weekly volume and add recovery.
- Bias exercise selection toward movements already in the athlete's history, \
continuing their load progression where it exists. Suggest concrete next \
loads (e.g. "67.5 kg" or "+2.5 kg from last week").
- For rest days use focus "Rest", an empty exercises list, and \
target_duration_min 0. For cardio/conditioning days, describe the work in \
the description and leave exercises empty.
- weekday is 0=Monday … 6=Sunday.

Keep the rationale to a few sentences: what drove the week's shape (goal, \
layoff, recovery, progression).\
"""


def generate_program(context: dict) -> dict:
    """Send ``context`` to Claude and return a validated weekly program.

    The only place that touches the network and ``ANTHROPIC_API_KEY``. Raises
    :class:`CoachError` with a clean message on a missing key, an API failure,
    or an unreadable response — the page surfaces it via ``st.error``.
    """
    import anthropic  # local import: keeps the data half import-light

    api_key = config.load().anthropic_api_key
    if not api_key:
        raise CoachError(
            "ANTHROPIC_API_KEY is not set. Add it to your .env to generate "
            "a program."
        )

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(context)}],
            output_config={
                "format": {"type": "json_schema", "schema": PROGRAM_SCHEMA}
            },
        )
    except anthropic.AuthenticationError as exc:
        logger.exception("Anthropic auth failed")
        raise CoachError(
            "Anthropic rejected the API key. Check ANTHROPIC_API_KEY."
        ) from exc
    except anthropic.APIError as exc:
        logger.exception("Anthropic API call failed")
        raise CoachError(f"Program generation failed: {exc}") from exc

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        raise CoachError("The model returned no program. Try again.")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.exception("Program response was not valid JSON: %s", text[:500])
        raise CoachError("The model returned an unreadable program.") from exc


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
