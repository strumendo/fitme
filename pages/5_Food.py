"""Food page — meal-by-meal entries, per-day totals, range trends.

Manual macros for now (no external nutrient DB lookup — that's a possible
later phase). Reads via ``fitme.queries``, writes via ``fitme.repository``.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from fitme import repository
from fitme.db import connect
from fitme.logging_config import setup as setup_logging
from fitme.queries import food_log_range, food_macros_summary

setup_logging()
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="fitme — Food",
    page_icon=":fork_and_knife:",
    layout="wide",
)
st.title("Food")

TODAY = date.today()
DEFAULT_DAYS = 14


# ---------------------------------------------------------------------------
# Add entry
# ---------------------------------------------------------------------------

st.header("Add entry")

with st.form("food_entry_form", clear_on_submit=True):
    c1, c2 = st.columns([1, 1])
    entry_date = c1.date_input("Date", value=TODAY, max_value=TODAY)
    meal = c2.selectbox(
        "Meal", ["breakfast", "lunch", "dinner", "snack", "other"]
    )
    description = st.text_input(
        "Description", placeholder="oatmeal + banana"
    )
    c3, c4, c5, c6 = st.columns(4)
    kcal = c3.number_input("kcal", min_value=0.0, step=10.0, value=0.0)
    protein = c4.number_input("protein (g)", min_value=0.0, step=1.0, value=0.0)
    carbs = c5.number_input("carbs (g)", min_value=0.0, step=1.0, value=0.0)
    fat = c6.number_input("fat (g)", min_value=0.0, step=1.0, value=0.0)
    notes = st.text_area("Notes", height=70)
    submitted = st.form_submit_button("Save entry", type="primary")
    if submitted:
        if not description.strip():
            st.error("Description is required.")
        else:
            with connect() as conn:
                repository.insert_food_log(
                    conn,
                    day=entry_date,
                    description=description.strip(),
                    meal=meal,
                    kcal=kcal or None,
                    protein_g=protein or None,
                    carbs_g=carbs or None,
                    fat_g=fat or None,
                    notes=notes.strip() or None,
                )
            logger.info(
                "Added food entry: %s on %s (%s kcal)",
                description, entry_date.isoformat(), kcal,
            )
            st.success(f"Saved {description} on {entry_date.isoformat()}.")
            st.rerun()


# ---------------------------------------------------------------------------
# Day view
# ---------------------------------------------------------------------------

st.header("Day view")

view_date = st.date_input(
    "Day", value=TODAY, max_value=TODAY, key="food_day_view"
)

with connect() as conn:
    day_rows = food_log_range(conn, view_date, view_date)

if not day_rows:
    st.caption(f"No entries on {view_date.isoformat()}.")
else:
    totals = {
        "kcal": sum((r["kcal"] or 0) for r in day_rows),
        "protein_g": sum((r["protein_g"] or 0) for r in day_rows),
        "carbs_g": sum((r["carbs_g"] or 0) for r in day_rows),
        "fat_g": sum((r["fat_g"] or 0) for r in day_rows),
    }
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("kcal", f"{totals['kcal']:.0f}")
    mc2.metric("protein", f"{totals['protein_g']:.0f} g")
    mc3.metric("carbs", f"{totals['carbs_g']:.0f} g")
    mc4.metric("fat", f"{totals['fat_g']:.0f} g")

    macro_kcal = {
        "protein": totals["protein_g"] * 4,
        "carbs": totals["carbs_g"] * 4,
        "fat": totals["fat_g"] * 9,
    }
    if sum(macro_kcal.values()) > 0:
        st.bar_chart(
            pd.DataFrame({"kcal": macro_kcal}),
            horizontal=True,
        )

    st.subheader("Entries")
    for row in day_rows:
        summary = (
            f"[{row['meal'] or 'meal'}] {row['description']} — "
            f"{int(row['kcal']) if row['kcal'] else '—'} kcal"
        )
        with st.expander(summary, expanded=False):
            with st.form(f"edit_food_{row['food_id']}"):
                ec1, ec2 = st.columns([1, 2])
                e_meal = ec1.selectbox(
                    "Meal",
                    ["breakfast", "lunch", "dinner", "snack", "other"],
                    index=(
                        ["breakfast", "lunch", "dinner", "snack", "other"].index(
                            row["meal"]
                        )
                        if row["meal"] in
                        {"breakfast", "lunch", "dinner", "snack", "other"}
                        else 4
                    ),
                    key=f"food_meal_{row['food_id']}",
                )
                e_desc = ec2.text_input(
                    "Description",
                    value=row["description"],
                    key=f"food_desc_{row['food_id']}",
                )
                fc1, fc2, fc3, fc4 = st.columns(4)
                e_kcal = fc1.number_input(
                    "kcal", min_value=0.0, step=10.0,
                    value=float(row["kcal"] or 0.0),
                    key=f"food_kcal_{row['food_id']}",
                )
                e_protein = fc2.number_input(
                    "protein (g)", min_value=0.0, step=1.0,
                    value=float(row["protein_g"] or 0.0),
                    key=f"food_p_{row['food_id']}",
                )
                e_carbs = fc3.number_input(
                    "carbs (g)", min_value=0.0, step=1.0,
                    value=float(row["carbs_g"] or 0.0),
                    key=f"food_c_{row['food_id']}",
                )
                e_fat = fc4.number_input(
                    "fat (g)", min_value=0.0, step=1.0,
                    value=float(row["fat_g"] or 0.0),
                    key=f"food_f_{row['food_id']}",
                )
                e_notes = st.text_area(
                    "Notes",
                    value=row["notes"] or "",
                    height=60,
                    key=f"food_notes_{row['food_id']}",
                )
                bc1, bc2 = st.columns(2)
                save_clicked = bc1.form_submit_button("Save", type="primary")
                delete_clicked = bc2.form_submit_button("Delete")
                if save_clicked:
                    if not e_desc.strip():
                        st.error("Description is required.")
                    else:
                        with connect() as conn:
                            repository.update_food_log(
                                conn, row["food_id"],
                                description=e_desc.strip(),
                                meal=e_meal,
                                kcal=e_kcal or None,
                                protein_g=e_protein or None,
                                carbs_g=e_carbs or None,
                                fat_g=e_fat or None,
                                notes=e_notes.strip() or None,
                            )
                        logger.info("Updated food_log %s", row["food_id"])
                        st.rerun()
                if delete_clicked:
                    with connect() as conn:
                        repository.delete_food_log(conn, row["food_id"])
                    logger.info("Deleted food_log %s", row["food_id"])
                    st.rerun()


# ---------------------------------------------------------------------------
# Range trends
# ---------------------------------------------------------------------------

st.header("Range trends")


def _set_range(days: int) -> None:
    st.session_state["food_range"] = (
        TODAY - timedelta(days=days - 1),
        TODAY,
    )


if "food_range" not in st.session_state:
    st.session_state["food_range"] = (
        TODAY - timedelta(days=DEFAULT_DAYS - 1),
        TODAY,
    )

c7, c14, c30, _ = st.columns([1, 1, 1, 7])
c7.button("7d", on_click=_set_range, args=(7,), use_container_width=True)
c14.button("14d", on_click=_set_range, args=(14,), use_container_width=True)
c30.button("30d", on_click=_set_range, args=(30,), use_container_width=True)

range_value = st.date_input(
    "Date range",
    value=st.session_state["food_range"],
    max_value=TODAY,
    key="food_range",
)
if not (isinstance(range_value, tuple) and len(range_value) == 2):
    st.warning("Pick both a start and an end date.")
    st.stop()
start, end = range_value
if start > end:
    st.warning("Start date is after end date.")
    st.stop()

with connect() as conn:
    summary = food_macros_summary(conn, start, end)

if not summary:
    st.info("No entries in this range.")
    st.stop()

idx = pd.date_range(start=start, end=end, freq="D")
df = pd.DataFrame(summary)
df["date"] = pd.to_datetime(df["date"])
df = df.set_index("date").reindex(idx).fillna(0.0)

avg_kcal = df["kcal"].replace(0, pd.NA).mean()
days_logged = int((df["entries"] > 0).sum())

mc1, mc2, mc3 = st.columns(3)
mc1.metric("Days in range", len(df))
mc2.metric("Days logged", days_logged)
mc3.metric(
    "Avg kcal / logged day",
    f"{avg_kcal:.0f}" if pd.notna(avg_kcal) else "—",
)

st.subheader("Daily kcal")
st.bar_chart(df[["kcal"]])

st.subheader("Daily macros (g)")
st.bar_chart(df[["protein_g", "carbs_g", "fat_g"]])
