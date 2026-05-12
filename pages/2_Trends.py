"""Trends page — multi-day line charts and period summary cards.

Run via the multi-page Streamlit app::

    uv run streamlit run app.py

The "Today" page (``app.py``) is the landing; this file is auto-discovered as
the second page by Streamlit's ``pages/`` convention.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from fitme.analysis import period_delta, rolling, to_dataframe
from fitme.db import connect
from fitme.logging_config import setup as setup_logging
from fitme.queries import (
    body_battery_range,
    daily_summary_range,
    heart_rate_range,
    hrv_range,
    sleep_range,
    stress_range,
    weight_range,
)

setup_logging()
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="fitme — Trends",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
)
st.title("Trends")

TODAY = date.today()
DEFAULT_DAYS = 30


def _set_range(days: int) -> None:
    st.session_state["trends_range"] = (TODAY - timedelta(days=days - 1), TODAY)


if "trends_range" not in st.session_state:
    st.session_state["trends_range"] = (
        TODAY - timedelta(days=DEFAULT_DAYS - 1),
        TODAY,
    )

c7, c30, c90, _ = st.columns([1, 1, 1, 7])
c7.button("7d", on_click=_set_range, args=(7,), use_container_width=True)
c30.button("30d", on_click=_set_range, args=(30,), use_container_width=True)
c90.button("90d", on_click=_set_range, args=(90,), use_container_width=True)

range_value = st.date_input(
    "Date range",
    value=st.session_state["trends_range"],
    max_value=TODAY,
    key="trends_range",
)
if not (isinstance(range_value, tuple) and len(range_value) == 2):
    st.warning("Pick both a start and an end date.")
    st.stop()
start, end = range_value
if start > end:
    st.warning("Start date is after end date.")
    st.stop()
range_days = (end - start).days + 1

with connect() as conn:
    summary_rows = daily_summary_range(conn, start, end)
    hr_rows = heart_rate_range(conn, start, end)
    sleep_raw = sleep_range(conn, start, end)
    weight_rows = weight_range(conn, start, end)
    bb_rows = body_battery_range(conn, start, end)
    stress_rows = stress_range(conn, start, end)
    hrv_rows = hrv_range(conn, start, end)

summary_df = to_dataframe(
    summary_rows, ["steps", "calories_kcal", "active_minutes"], start, end
)
hr_df = to_dataframe(hr_rows, ["resting_bpm"], start, end)
sleep_df = to_dataframe(sleep_raw, ["total_seconds"], start, end)
sleep_df["sleep_hours"] = sleep_df["total_seconds"] / 3600.0
weight_df = to_dataframe(weight_rows, ["weight_kg"], start, end)
bb_df = to_dataframe(bb_rows, ["highest", "lowest", "charged", "drained"], start, end)
stress_df = to_dataframe(stress_rows, ["avg_level", "max_level"], start, end)
hrv_df = to_dataframe(hrv_rows, ["last_night_avg", "weekly_avg"], start, end)


def _format(value: float | None, fmt: str, unit: str) -> str:
    if value is None:
        return "n/a"
    body = fmt.format(value)
    return f"{body} {unit}" if unit else body


def render_metric(
    title: str,
    df: pd.DataFrame,
    col: str,
    fmt: str,
    unit: str,
    *,
    rolling_default: bool,
) -> None:
    st.subheader(title)
    if df.empty or col not in df.columns or df[col].dropna().empty:
        st.caption("No data in this range.")
        return
    cur, prev = period_delta(df, col, range_days)
    delta = None
    if cur is not None and prev is not None:
        delta = f"{cur - prev:+{fmt[1:]}}"
    st.metric(f"{title} (avg)", _format(cur, fmt, unit), delta=delta)
    show_rolling = st.toggle(
        "7-day rolling average",
        value=rolling_default,
        key=f"roll_{col}",
    )
    plot_df = rolling(df[[col]], window=7) if show_rolling else df[[col]]
    st.line_chart(plot_df)


render_metric("Steps", summary_df, "steps", "{:.0f}", "", rolling_default=False)
render_metric(
    "Calories", summary_df, "calories_kcal", "{:.0f}", "kcal", rolling_default=False
)
render_metric(
    "Active minutes",
    summary_df,
    "active_minutes",
    "{:.0f}",
    "min",
    rolling_default=False,
)
render_metric(
    "Resting HR", hr_df, "resting_bpm", "{:.0f}", "bpm", rolling_default=True
)
render_metric(
    "Sleep duration",
    sleep_df,
    "sleep_hours",
    "{:.1f}",
    "h",
    rolling_default=False,
)
render_metric("Weight", weight_df, "weight_kg", "{:.1f}", "kg", rolling_default=True)
render_metric(
    "Body battery (peak)",
    bb_df,
    "highest",
    "{:.0f}",
    "",
    rolling_default=True,
)
render_metric(
    "Stress (avg)", stress_df, "avg_level", "{:.0f}", "", rolling_default=True
)
render_metric(
    "HRV (last night)",
    hrv_df,
    "last_night_avg",
    "{:.0f}",
    "ms",
    rolling_default=True,
)
