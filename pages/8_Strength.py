"""Strength page — per-exercise progression over a date range.

Plots max weight, total volume (weight × reps summed across sets), and
estimated 1RM (Epley) per session, plus a table of the recent sets for the
chosen exercise. Reads from the ``exercise_set`` table (joined with
``training_log`` for dates).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from fitme.db import connect
from fitme.logging_config import setup as setup_logging
from fitme.queries import exercise_history, exercise_names

setup_logging()
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="fitme — Strength",
    page_icon=":weight_lifter:",
    layout="wide",
)
st.title("Strength")

TODAY = date.today()
DEFAULT_DAYS = 30


def _set_range(days: int) -> None:
    st.session_state["strength_range"] = (
        TODAY - timedelta(days=days - 1),
        TODAY,
    )


if "strength_range" not in st.session_state:
    st.session_state["strength_range"] = (
        TODAY - timedelta(days=DEFAULT_DAYS - 1),
        TODAY,
    )

c7, c30, c90, _ = st.columns([1, 1, 1, 7])
c7.button("7d", on_click=_set_range, args=(7,), use_container_width=True)
c30.button("30d", on_click=_set_range, args=(30,), use_container_width=True)
c90.button("90d", on_click=_set_range, args=(90,), use_container_width=True)

range_value = st.date_input(
    "Date range",
    value=st.session_state["strength_range"],
    max_value=TODAY,
    key="strength_range",
)
if not (isinstance(range_value, tuple) and len(range_value) == 2):
    st.warning("Pick both a start and an end date.")
    st.stop()
start, end = range_value
if start > end:
    st.warning("Start date is after end date.")
    st.stop()

with connect() as conn:
    names = exercise_names(conn, start, end)

if not names:
    st.info(
        "No sets logged in this range. Head to the Training page, expand "
        "a session, and add sets under it."
    )
    st.stop()

selected_name = st.selectbox("Exercise", options=names)

with connect() as conn:
    history = exercise_history(conn, selected_name, start, end)

if not history:
    st.info(f"No sets for {selected_name} in this range.")
    st.stop()

df = pd.DataFrame(history)
df["date"] = pd.to_datetime(df["date"])
df["weight_kg"] = pd.to_numeric(df["weight_kg"], errors="coerce")
df["reps"] = pd.to_numeric(df["reps"], errors="coerce")
df["volume"] = df["weight_kg"] * df["reps"]
df["epley_1rm"] = df["weight_kg"] * (1 + df["reps"] / 30.0)

agg = df.groupby("date").agg(
    max_weight=("weight_kg", "max"),
    total_volume=("volume", "sum"),
    best_1rm=("epley_1rm", "max"),
    sets=("set_id", "count"),
)

m1, m2, m3 = st.columns(3)
m1.metric("Sessions", len(agg))
m1.metric("Total sets", int(agg["sets"].sum()))
max_w = agg["max_weight"].max()
m2.metric(
    "Best weight (kg)",
    f"{max_w:.1f}" if pd.notna(max_w) else "—",
)
best_1rm = agg["best_1rm"].max()
m3.metric(
    "Best est. 1RM (kg)",
    f"{best_1rm:.1f}" if pd.notna(best_1rm) else "—",
)

st.subheader("Max weight per session")
st.line_chart(agg[["max_weight"]])

st.subheader("Total volume per session (kg × reps)")
st.line_chart(agg[["total_volume"]])

st.subheader("Estimated 1RM per session (Epley)")
st.caption(
    "Epley: weight × (1 + reps / 30). Best set per session is plotted."
)
st.line_chart(agg[["best_1rm"]])

st.subheader("Recent sets")
recent = df.sort_values(["date", "set_number"], ascending=[False, False]).head(30)
table = recent[["date", "set_number", "weight_kg", "reps", "rpe"]].copy()
table["date"] = table["date"].dt.strftime("%Y-%m-%d")
table.columns = ["date", "set #", "kg", "reps", "RPE"]
st.dataframe(table, use_container_width=True, hide_index=True)
