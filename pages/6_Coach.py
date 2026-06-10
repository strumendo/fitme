"""Coach page — an LLM-generated weekly training program.

Reads the active goal + a data snapshot (training history, layoff,
bodyweight trend, recovery) via ``fitme.coach.build_context``, then asks
Claude for a 7-day program on demand (``fitme.coach.generate_program``).
The generated program is held in ``session_state`` so reruns don't re-call
the API. Without ``ANTHROPIC_API_KEY`` the snapshot still renders; only
generation is disabled.
"""
from __future__ import annotations

import logging
from datetime import date

import pandas as pd
import streamlit as st

from fitme import coach, config, repository
from fitme.db import connect
from fitme.logging_config import setup as setup_logging
from fitme.queries import active_goal

setup_logging()
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="fitme — Coach",
    page_icon=":brain:",
    layout="wide",
)
st.title("Coach")

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
TODAY = date.today()


def _plan_description(day: dict) -> str:
    """Flatten a program day into a single plan-slot description.

    The plan's ``description`` is one text field, so fold the day's
    description and per-exercise set/rep/load detail into it — otherwise the
    exercise prescription would be lost when saving to ``training_plan``.
    """
    parts: list[str] = []
    if day.get("description"):
        parts.append(day["description"])
    for e in day.get("exercises") or []:
        parts.append(
            f"{e['name']} {e['sets']}×{e['reps']} @ {e['suggested_load']}"
        )
    return " — ".join(parts)

with connect() as conn:
    goal = active_goal(conn)

if not goal:
    st.info(
        "Set a goal on the Training page first — it drives the program."
    )
    st.stop()

with connect() as conn:
    context = coach.build_context(conn, goal, today=TODAY)

# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

st.subheader("Snapshot")

g = context["goal"]
st.markdown(
    f"Goal: **{g['preset']}** · {g['days_per_week'] or '—'} days/week"
    + (f" · ~{g['session_length_min']} min/session"
       if g["session_length_min"] else "")
)

hist = context["history"]
bw = context["bodyweight"]
rec = context["recovery"]
layoff = context["layoff_days"]

s1, s2, s3, s4 = st.columns(4)
s1.metric("Sessions / week (90d)", hist["sessions_per_week"])
s2.metric(
    "Days since last session",
    layoff if layoff is not None else "—",
)
s3.metric(
    "Bodyweight (kg)",
    f"{bw['latest_kg']:.1f}" if bw else "—",
    delta=(f"{bw['delta_over_window_kg']:+.1f} (90d)" if bw else None),
)
s4.metric(
    "Avg sleep (h, 14d)",
    rec["avg_sleep_hours"] if rec["avg_sleep_hours"] is not None else "—",
)

if hist["exercises"]:
    with st.expander("Exercise progression (90d)"):
        prog = pd.DataFrame(
            [
                {
                    "exercise": e["name"],
                    "sessions": e["sessions"],
                    "latest kg": e["latest_weight_kg"],
                    "latest reps": e["latest_reps"],
                    "Δ kg": e["weight_delta_kg"],
                }
                for e in hist["exercises"]
            ]
        )
        st.dataframe(prog, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

st.subheader("Weekly program")

if not config.load().anthropic_api_key:
    st.warning(
        "Set ANTHROPIC_API_KEY in your .env to generate a program. "
        "The snapshot above works without it."
    )
    st.stop()

if st.button("Generate program", type="primary"):
    with st.spinner("Asking the coach…"):
        try:
            st.session_state["coach_program"] = coach.generate_program(context)
            logger.info("Generated weekly program for goal %s", g["preset"])
        except coach.CoachError as exc:
            st.session_state.pop("coach_program", None)
            st.error(str(exc))

program = st.session_state.get("coach_program")
if program:
    st.caption(program.get("rationale", ""))
    week = sorted(program.get("week", []), key=lambda d: d["weekday"])
    for day in week:
        wd = WEEKDAY_NAMES[day["weekday"]]
        dur = day.get("target_duration_min") or 0
        header = f"**{wd} — {day['focus']}**" + (f" · {dur} min" if dur else "")
        st.markdown(header)
        if day.get("description"):
            st.caption(day["description"])
        exercises = day.get("exercises") or []
        if exercises:
            ex_df = pd.DataFrame(
                [
                    {
                        "exercise": e["name"],
                        "sets": e["sets"],
                        "reps": e["reps"],
                        "load": e["suggested_load"],
                    }
                    for e in exercises
                ]
            )
            st.dataframe(ex_df, use_container_width=True, hide_index=True)

    # ----- Save as plan -----
    st.divider()
    st.caption(
        "Saving writes this week into your training plan as a new version "
        f"effective {TODAY.isoformat()} (older versions are kept). The Today "
        "page then shows each day's recommended session."
    )
    if st.button("Save this week as my plan"):
        with connect() as conn:
            for day in week:
                repository.upsert_training_plan_slot(
                    conn,
                    effective_from=TODAY,
                    weekday=day["weekday"],
                    slot=0,
                    activity_type=day["focus"],
                    description=_plan_description(day) or None,
                    target_duration_min=day.get("target_duration_min") or None,
                )
        logger.info("Saved generated program as plan effective %s", TODAY)
        st.success("Saved as your training plan.")
