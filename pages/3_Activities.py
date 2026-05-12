"""Activities page — list Garmin activities with type and date-range filters.

Each row is expandable to inspect the raw Garmin payload. Reads from the
``activities`` table populated by the ``activities`` ingest metric::

    uv run python -m fitme.ingest --since 30d --metrics activities
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from fitme.db import connect
from fitme.logging_config import setup as setup_logging
from fitme.queries import activities_range, activity_types

setup_logging()
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="fitme — Activities",
    page_icon=":weight_lifter:",
    layout="wide",
)
st.title("Activities")

TODAY = date.today()
DEFAULT_DAYS = 30


def _set_range(days: int) -> None:
    st.session_state["activities_range"] = (
        TODAY - timedelta(days=days - 1),
        TODAY,
    )


if "activities_range" not in st.session_state:
    st.session_state["activities_range"] = (
        TODAY - timedelta(days=DEFAULT_DAYS - 1),
        TODAY,
    )

c7, c30, c90, _ = st.columns([1, 1, 1, 7])
c7.button("7d", on_click=_set_range, args=(7,), use_container_width=True)
c30.button("30d", on_click=_set_range, args=(30,), use_container_width=True)
c90.button("90d", on_click=_set_range, args=(90,), use_container_width=True)

range_value = st.date_input(
    "Date range",
    value=st.session_state["activities_range"],
    max_value=TODAY,
    key="activities_range",
)
if not (isinstance(range_value, tuple) and len(range_value) == 2):
    st.warning("Pick both a start and an end date.")
    st.stop()
start, end = range_value
if start > end:
    st.warning("Start date is after end date.")
    st.stop()

with connect() as conn:
    types_available = activity_types(conn, start, end)
    type_choice = st.selectbox(
        "Activity type",
        options=["(all)", *types_available],
        index=0,
    )
    rows = activities_range(
        conn,
        start,
        end,
        activity_type=None if type_choice == "(all)" else type_choice,
    )

if not rows:
    st.info("No activities in this range. Run the ingest CLI with `--metrics activities`.")
    st.stop()

st.caption(f"{len(rows)} activities")


def _format_duration(seconds: int | None) -> str:
    if not seconds:
        return ""
    hrs, rem = divmod(int(seconds), 3600)
    mins, secs = divmod(rem, 60)
    if hrs:
        return f"{hrs}h{mins:02d}m"
    return f"{mins}m{secs:02d}s"


def _format_distance(meters: float | None) -> str:
    if meters is None:
        return ""
    return f"{meters / 1000:.2f} km"


table = pd.DataFrame(
    [
        {
            "start": r["start_time"][:16].replace("T", " "),
            "type": r["type"] or "",
            "name": r["name"] or "",
            "duration": _format_duration(r["duration_s"]),
            "distance": _format_distance(r["distance_m"]),
            "calories": int(r["calories_kcal"]) if r["calories_kcal"] else None,
            "avg HR": r["avg_hr_bpm"],
            "max HR": r["max_hr_bpm"],
        }
        for r in rows
    ]
)
st.dataframe(table, use_container_width=True, hide_index=True)

st.subheader("Details")
for r in rows:
    label = (
        f"{r['start_time'][:16].replace('T', ' ')} — "
        f"{r['type'] or 'activity'}: {r['name'] or ''}"
    )
    with st.expander(label):
        st.json(json.loads(r["raw_json"]))
