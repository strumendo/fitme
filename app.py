"""Streamlit dashboard entry point — "Today" landing page.

The fitme dashboard is a multi-page Streamlit app:

- This file (``app.py``) is the landing "Today" page — single-day snapshot.
- ``pages/2_Trends.py`` — multi-day line charts and period deltas.

Both pages read from the local SQLite DB. If a date has no row, the Today
page offers a one-click button that calls the ingest pipeline for that date
and reruns. Background ingest still happens manually via
``uv run python -m fitme.ingest``.

Run with::

    uv run streamlit run app.py
"""
from __future__ import annotations

import json
import logging
from datetime import date

import streamlit as st

from fitme.db import connect
from fitme.garmin import GarminAuthError, get_client
from fitme.ingest import (
    ingest_daily_summary,
    ingest_heart_rate,
    ingest_sleep,
    ingest_weight,
)
from fitme.logging_config import setup as setup_logging
from fitme.queries import (
    get_daily_summary,
    get_heart_rate,
    get_sleep,
    get_weight,
)

setup_logging()
logger = logging.getLogger(__name__)

st.set_page_config(page_title="fitme — Today", page_icon=":runner:", layout="wide")
st.title("Today")

selected = st.date_input("Date", value=date.today(), max_value=date.today())


def _fetch_from_garmin(day: date) -> bool:
    """Pull and store the day's data from Garmin. Returns True on success."""
    try:
        client = get_client()
    except GarminAuthError as err:
        logger.warning("Garmin client unavailable: %s", err)
        st.error(str(err))
        return False
    with connect() as conn:
        ingest_daily_summary(client, conn, day)
        ingest_heart_rate(client, conn, day)
        ingest_sleep(client, conn, day)
        ingest_weight(client, conn, day)
    return True


with connect() as conn:
    summary = get_daily_summary(conn, selected)
    hr = get_heart_rate(conn, selected)
    sleep_row = get_sleep(conn, selected)
    weight_row = get_weight(conn, selected)

if not any((summary, hr, sleep_row, weight_row)):
    st.info(f"No data stored for {selected.isoformat()}.")
    if st.button(f"Fetch from Garmin for {selected.isoformat()}"):
        with st.spinner("Fetching from Garmin..."):
            ok = _fetch_from_garmin(selected)
        if ok:
            st.rerun()
    st.stop()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Daily summary")
    if summary:
        steps = summary["steps"] or 0
        kcal = summary["calories_kcal"] or 0
        dist_m = summary["distance_m"] or 0
        st.metric("Steps", f"{steps:,}")
        st.metric("Calories", f"{kcal:.0f} kcal")
        st.metric("Distance", f"{dist_m / 1000:.2f} km")
    else:
        st.caption("No daily summary stored.")

with col2:
    st.subheader("Heart rate")
    if hr:
        st.metric("Resting HR", f"{hr['resting_bpm'] or 'n/a'} bpm")
        st.metric("Max HR", f"{hr['max_bpm'] or 'n/a'} bpm")
    else:
        st.caption("No heart-rate stored.")

col3, col4 = st.columns(2)

with col3:
    st.subheader("Sleep")
    if sleep_row and sleep_row["total_seconds"]:
        st.metric("Total sleep", f"{sleep_row['total_seconds'] / 3600:.1f} h")
        deep = (sleep_row["deep_seconds"] or 0) / 3600
        rem = (sleep_row["rem_seconds"] or 0) / 3600
        st.metric("Deep / REM", f"{deep:.1f} h / {rem:.1f} h")
    else:
        st.caption("No sleep stored.")

with col4:
    st.subheader("Weight")
    if weight_row and weight_row["weight_kg"]:
        st.metric("Weight", f"{weight_row['weight_kg']:.1f} kg")
        if weight_row["body_fat_pct"]:
            st.metric("Body fat", f"{weight_row['body_fat_pct']:.1f} %")
    else:
        st.caption("No weight stored.")

if summary and summary["raw_json"]:
    with st.expander("Raw daily-summary payload"):
        st.json(json.loads(summary["raw_json"]))
