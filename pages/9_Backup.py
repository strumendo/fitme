"""Backup page — one-click SQLite snapshot + CSV bundle download.

Both downloads stream bytes directly to the browser; nothing persists
server-side. Use the CLI (``uv run python -m fitme.export``) when you want
the dumps written to ``data/exports/`` instead.
"""
from __future__ import annotations

import io
import logging
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from fitme.config import load as load_settings
from fitme.db import connect
from fitme.export import (
    export_csv,
    export_sqlite,
    table_row_counts,
)
from fitme.logging_config import setup as setup_logging

setup_logging()
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="fitme — Backup",
    page_icon=":floppy_disk:",
    layout="wide",
)
st.title("Backup")

st.caption(
    "Download a portable copy of your fitme database. SQLite is the "
    "lossless format; CSV is a per-table dump for spreadsheets."
)


def _utc_stamp() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _build_sqlite_bytes(src_path: Path) -> bytes:
    """Return a fresh ``.backup`` copy of the source DB as bytes."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        export_sqlite(src_path, tmp_path)
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)


def _build_csv_zip(*, include_raw: bool) -> bytes:
    """Build a CSV-per-table ZIP in memory."""
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td)
        with connect() as conn:
            export_csv(conn, out_dir, include_raw=include_raw)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(out_dir.glob("*.csv")):
                zf.write(path, arcname=path.name)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Row count summary
# ---------------------------------------------------------------------------

src_path = load_settings().db_path

try:
    with connect() as conn:
        counts = table_row_counts(conn)
except sqlite3.Error as err:
    logger.exception("Failed to read row counts")
    st.error(f"Could not read the database: {err}")
    st.stop()

st.subheader("Tables in the database")
if counts:
    df = pd.DataFrame(
        [{"table": t, "rows": n} for t, n in sorted(counts.items())]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)
    total = sum(counts.values())
    st.caption(f"Total rows across {len(counts)} tables: {total:,}.")
else:
    st.info("No user tables found. Nothing to export.")
    st.stop()

# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------

st.subheader("Downloads")

stamp = _utc_stamp()
col_sqlite, col_csv = st.columns(2)

with col_sqlite:
    st.markdown("**SQLite snapshot**")
    st.caption(
        "Lossless — every column including `raw_json` payloads. "
        "Restore by stopping Streamlit, replacing `data/fitme.db`, and "
        "starting again."
    )
    sqlite_bytes = _build_sqlite_bytes(src_path)
    st.download_button(
        label=f"Download fitme-{stamp}.db",
        data=sqlite_bytes,
        file_name=f"fitme-{stamp}.db",
        mime="application/vnd.sqlite3",
        type="primary",
        use_container_width=True,
    )
    st.caption(f"{len(sqlite_bytes) / 1024:.1f} KB ready.")

with col_csv:
    st.markdown("**CSV bundle (ZIP)**")
    include_raw = st.toggle(
        "Include raw_json columns",
        value=False,
        help=(
            "raw_json holds the full Garmin payload per row — useful for "
            "debugging, balloons the file size otherwise."
        ),
    )
    csv_bytes = _build_csv_zip(include_raw=include_raw)
    st.download_button(
        label=f"Download fitme-{stamp}.zip",
        data=csv_bytes,
        file_name=f"fitme-{stamp}.zip",
        mime="application/zip",
        type="primary",
        use_container_width=True,
    )
    st.caption(f"{len(csv_bytes) / 1024:.1f} KB ready.")

st.divider()
st.caption(
    "Prefer the CLI? Run "
    "`uv run python -m fitme.export sqlite` or "
    "`uv run python -m fitme.export csv` to write dumps under "
    "`data/exports/`."
)
