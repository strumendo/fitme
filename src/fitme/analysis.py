"""Time-series transforms for the trends dashboard.

This module is the bridge between ``queries.py`` (which returns plain
``list[dict]``) and the Streamlit pages (which want pandas DataFrames). The DB
layer deliberately stays free of pandas so it can be tested without pulling
DataFrames into the loop — every pandas import lives here or in pages.
"""
from __future__ import annotations

from datetime import date

import pandas as pd


def to_dataframe(
    rows: list[dict], value_cols: list[str], start: date, end: date
) -> pd.DataFrame:
    """Build a date-indexed DataFrame over ``[start, end]`` from query rows.

    Missing days appear as ``NaN`` rather than being silently dropped, so
    ``st.line_chart`` renders them as gaps instead of straight-lining over
    them.
    """
    idx = pd.date_range(start=start, end=end, freq="D")
    if not rows:
        return pd.DataFrame(index=idx, columns=value_cols, dtype="float64")
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    missing = [c for c in value_cols if c not in df.columns]
    for c in missing:
        df[c] = pd.NA
    return df[value_cols].reindex(idx)


def rolling(df: pd.DataFrame, window: int = 7) -> pd.DataFrame:
    """Return a copy of ``df`` with rolling-mean columns appended as ``<col>_avg``."""
    avg = df.rolling(window=window, min_periods=1).mean()
    avg.columns = [f"{c}_avg" for c in df.columns]
    return df.join(avg)


def period_delta(
    df: pd.DataFrame, col: str, days: int
) -> tuple[float | None, float | None]:
    """Mean of ``col`` over the trailing ``days`` and the ``days`` before that.

    Returns ``(current, previous)``. Either side may be ``None`` when there is
    no data in that window.
    """
    if df.empty or col not in df.columns:
        return None, None
    end = df.index.max()
    cur_start = end - pd.Timedelta(days=days - 1)
    prev_end = cur_start - pd.Timedelta(days=1)
    prev_start = prev_end - pd.Timedelta(days=days - 1)
    cur = df.loc[cur_start:end, col].mean()
    prev = df.loc[prev_start:prev_end, col].mean()
    return (
        None if pd.isna(cur) else float(cur),
        None if pd.isna(prev) else float(prev),
    )
