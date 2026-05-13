"""Training page — weekly plan editor, session log, plan-vs-actual view.

Reads from ``training_plan``, ``training_log``, and ``activities`` (the
Garmin table). Writes go through ``fitme.repository`` — no inline SQL.

The plan is versioned by ``effective_from``: superseding a version inserts a
new set of rows with a newer date, leaving older rows in place so history
stays reproducible.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from fitme import repository
from fitme.db import connect
from fitme.logging_config import setup as setup_logging
from fitme.queries import (
    activities_range,
    plan_for_date,
    training_log_range,
    training_plan_versions,
)

setup_logging()
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="fitme — Training",
    page_icon=":weight_lifter:",
    layout="wide",
)
st.title("Training")

TODAY = date.today()
DEFAULT_DAYS = 14

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ---------------------------------------------------------------------------
# Weekly plan editor
# ---------------------------------------------------------------------------

st.header("Weekly plan")

with connect() as conn:
    plan_rows = plan_for_date(conn, TODAY)
    versions = training_plan_versions(conn)

if versions:
    st.caption(
        f"Active version: **{versions[0]}** — "
        f"{len(versions)} version(s) on record."
    )
else:
    st.caption("No plan yet. Add your first slot below.")

plan_by_day = {r["weekday"]: r for r in plan_rows}

plan_table = pd.DataFrame(
    [
        {
            "weekday": WEEKDAY_NAMES[i],
            "activity_type": (plan_by_day.get(i) or {}).get("activity_type", ""),
            "description": (plan_by_day.get(i) or {}).get("description") or "",
            "target_min": (plan_by_day.get(i) or {}).get("target_duration_min"),
        }
        for i in range(7)
    ]
)
st.dataframe(plan_table, use_container_width=True, hide_index=True)

with st.expander("Add or replace a slot", expanded=not plan_rows):
    with st.form("plan_slot_form", clear_on_submit=True):
        col_a, col_b, col_c = st.columns(3)
        weekday_label = col_a.selectbox("Weekday", WEEKDAY_NAMES)
        activity_type = col_b.text_input(
            "Activity type", placeholder="run, strength_lower, ride…"
        )
        target_min = col_c.number_input(
            "Target duration (min)", min_value=0, max_value=600, step=5, value=0
        )
        description = st.text_input("Description (optional)")
        effective_from = st.date_input(
            "Effective from",
            value=date.fromisoformat(versions[0]) if versions else TODAY,
            help=(
                "Pick a new date to supersede the current plan (history is "
                "preserved). Reuse the active version's date to edit it in place."
            ),
        )
        submitted = st.form_submit_button("Save slot", type="primary")
        if submitted:
            if not activity_type.strip():
                st.error("Activity type is required.")
            else:
                with connect() as conn:
                    repository.upsert_training_plan_slot(
                        conn,
                        effective_from=effective_from,
                        weekday=WEEKDAY_NAMES.index(weekday_label),
                        slot=0,
                        activity_type=activity_type.strip(),
                        description=description.strip() or None,
                        target_duration_min=int(target_min) or None,
                    )
                logger.info(
                    "Saved plan slot: %s %s @ %s",
                    weekday_label, activity_type, effective_from.isoformat(),
                )
                st.success(
                    f"Saved {weekday_label} = {activity_type} "
                    f"(effective {effective_from.isoformat()})."
                )
                st.rerun()

if plan_rows:
    with st.expander("Delete a slot"):
        slot_labels = {
            r["plan_id"]: (
                f"{WEEKDAY_NAMES[r['weekday']]} — {r['activity_type']} "
                f"(plan_id={r['plan_id']})"
            )
            for r in plan_rows
        }
        target = st.selectbox(
            "Slot",
            options=list(slot_labels.keys()),
            format_func=lambda pid: slot_labels[pid],
        )
        if st.button("Delete slot", type="secondary"):
            with connect() as conn:
                repository.delete_training_plan_slot(conn, target)
            logger.info("Deleted plan slot %s", target)
            st.rerun()


# ---------------------------------------------------------------------------
# Log a session
# ---------------------------------------------------------------------------

st.header("Log a session")

session_date = st.date_input(
    "Session date", value=TODAY, max_value=TODAY, key="log_session_date"
)

with connect() as conn:
    same_day_activities = activities_range(conn, session_date, session_date)

activity_options: dict[int | None, str] = {None: "(none)"}
for a in same_day_activities:
    label = (
        f"{a['start_time'][11:16]} — {a['type'] or 'activity'}: "
        f"{a['name'] or ''} ({(a['duration_s'] or 0) // 60} min)"
    )
    activity_options[a["activity_id"]] = label

with st.form("training_log_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    log_type = col1.text_input(
        "Activity type", placeholder="run, strength_lower, ride…"
    )
    log_duration = col2.number_input(
        "Duration (min)", min_value=0, max_value=600, step=5, value=0
    )
    col3, col4 = st.columns(2)
    log_effort = col3.slider("Perceived effort (1–10)", 1, 10, 5)
    garmin_id = col4.selectbox(
        "Link to Garmin activity",
        options=list(activity_options.keys()),
        format_func=lambda key: activity_options[key],
    )
    log_notes = st.text_area("Notes", height=70)
    submitted = st.form_submit_button("Save session", type="primary")
    if submitted:
        if not log_type.strip():
            st.error("Activity type is required.")
        else:
            with connect() as conn:
                repository.insert_training_log(
                    conn,
                    day=session_date,
                    activity_type=log_type.strip(),
                    duration_min=int(log_duration) or None,
                    perceived_effort=int(log_effort),
                    notes=log_notes.strip() or None,
                    garmin_activity_id=garmin_id,
                )
            logger.info(
                "Logged session: %s %s min on %s",
                log_type, log_duration, session_date.isoformat(),
            )
            st.success(f"Logged {log_type} on {session_date.isoformat()}.")
            st.rerun()


# ---------------------------------------------------------------------------
# Plan vs actual
# ---------------------------------------------------------------------------

st.header("Plan vs actual")


def _set_range(days: int) -> None:
    st.session_state["training_range"] = (
        TODAY - timedelta(days=days - 1),
        TODAY,
    )


if "training_range" not in st.session_state:
    st.session_state["training_range"] = (
        TODAY - timedelta(days=DEFAULT_DAYS - 1),
        TODAY,
    )

c7, c14, c30, _ = st.columns([1, 1, 1, 7])
c7.button("7d", on_click=_set_range, args=(7,), use_container_width=True)
c14.button("14d", on_click=_set_range, args=(14,), use_container_width=True)
c30.button("30d", on_click=_set_range, args=(30,), use_container_width=True)

range_value = st.date_input(
    "Date range",
    value=st.session_state["training_range"],
    max_value=TODAY,
    key="training_range",
)
if not (isinstance(range_value, tuple) and len(range_value) == 2):
    st.warning("Pick both a start and an end date.")
    st.stop()
start, end = range_value
if start > end:
    st.warning("Start date is after end date.")
    st.stop()

with connect() as conn:
    logs = training_log_range(conn, start, end)
    garmin_acts = activities_range(conn, start, end)
    by_date_plan = {
        d.isoformat(): plan_for_date(conn, d)
        for d in (start + timedelta(days=i) for i in range((end - start).days + 1))
    }

logs_by_date: dict[str, list[dict]] = {}
for row in logs:
    logs_by_date.setdefault(row["date"], []).append(row)

acts_by_date: dict[str, list[dict]] = {}
for row in garmin_acts:
    acts_by_date.setdefault(row["date"], []).append(row)


def _slot_for_day(plan: list[dict], weekday: int) -> dict | None:
    for row in plan:
        if row["weekday"] == weekday:
            return row
    return None


total_days = (end - start).days + 1
days_with_plan = 0
days_with_log = 0
for i in range(total_days):
    d = start + timedelta(days=i)
    plan = by_date_plan[d.isoformat()]
    if _slot_for_day(plan, d.weekday()):
        days_with_plan += 1
    if logs_by_date.get(d.isoformat()):
        days_with_log += 1

mc1, mc2, mc3 = st.columns(3)
mc1.metric("Days in range", total_days)
mc2.metric("Days with plan", days_with_plan)
mc3.metric("Days logged", days_with_log)

for i in range(total_days):
    d = start + timedelta(days=i)
    iso = d.isoformat()
    plan = by_date_plan[iso]
    planned = _slot_for_day(plan, d.weekday())
    logged = logs_by_date.get(iso, [])
    acts = acts_by_date.get(iso, [])
    header = f"**{iso}** ({WEEKDAY_NAMES[d.weekday()]})"
    if planned:
        target = (
            f" — target: {planned['activity_type']}"
            + (f" ({planned['target_duration_min']} min)"
               if planned["target_duration_min"] else "")
        )
        header += target
    elif not logged and not acts:
        continue
    with st.expander(header, expanded=False):
        if logged:
            st.markdown("**Logged sessions**")
            for row in logged:
                cols = st.columns([3, 1, 1, 3, 1])
                cols[0].write(row["activity_type"])
                cols[1].write(
                    f"{row['duration_min']} min" if row["duration_min"] else "—"
                )
                cols[2].write(
                    f"effort {row['perceived_effort']}"
                    if row["perceived_effort"] else "—"
                )
                cols[3].write(row["notes"] or "")
                if cols[4].button("Delete", key=f"del_log_{row['log_id']}"):
                    with connect() as conn:
                        repository.delete_training_log(conn, row["log_id"])
                    logger.info("Deleted training_log %s", row["log_id"])
                    st.rerun()
        else:
            st.caption("No logged session.")
        if acts:
            st.markdown("**Garmin activities**")
            for row in acts:
                st.write(
                    f"• {row['start_time'][11:16]} {row['type'] or ''} — "
                    f"{(row['duration_s'] or 0) // 60} min"
                    + (f", {row['distance_m'] / 1000:.2f} km"
                       if row["distance_m"] else "")
                )
