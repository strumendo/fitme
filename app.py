"""Streamlit dashboard entry point.

Run with:
    uv run streamlit run app.py
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import streamlit as st

from fitme.garmin import GarminAuthError, daily_summary, get_client, heart_rate
from fitme.logging_config import setup as setup_logging

setup_logging()
logger = logging.getLogger(__name__)

st.set_page_config(page_title="fitme", page_icon=":runner:", layout="wide")
st.title("fitme")

try:
    client = get_client()
except GarminAuthError as err:
    logger.warning("Garmin client unavailable: %s", err)
    st.error(str(err))
    st.stop()

selected = st.date_input("Date", value=date.today(), max_value=date.today())

summary: dict | None = None
hr: dict | None = None

col1, col2 = st.columns(2)

with col1:
    st.subheader("Daily summary")
    try:
        summary = daily_summary(client, selected)
    except Exception as err:  # noqa: BLE001 — surface any API error in the UI
        logger.exception("daily_summary failed for %s", selected)
        st.warning(f"Could not fetch summary: {err}")
    else:
        steps = summary.get("totalSteps", 0)
        kcal = summary.get("totalKilocalories", 0) or 0
        dist_km = (summary.get("totalDistanceMeters", 0) or 0) / 1000
        st.metric("Steps", f"{steps:,}")
        st.metric("Calories", f"{kcal:.0f} kcal")
        st.metric("Distance", f"{dist_km:.2f} km")

with col2:
    st.subheader("Heart rate")
    try:
        hr = heart_rate(client, selected)
    except Exception as err:  # noqa: BLE001
        logger.exception("heart_rate failed for %s", selected)
        st.warning(f"Could not fetch heart rate: {err}")
    else:
        st.metric("Resting HR", f"{hr.get('restingHeartRate', 'n/a')} bpm")
        st.metric("Max HR", f"{hr.get('maxHeartRate', 'n/a')} bpm")

if summary is not None:
    with st.expander("Raw summary payload"):
        st.json(summary)

st.caption(
    f"Window reference: {(selected - timedelta(days=7)).isoformat()} → {selected.isoformat()}"
)
