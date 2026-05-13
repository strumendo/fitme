"""Export / backup helpers for the fitme SQLite DB.

Two formats:

- **CSV** — one file per user table, written under a destination directory.
  By default skips the ``raw_json`` columns (they balloon the file size for
  little value outside debugging); flip ``include_raw`` to keep them.
- **SQLite snapshot** — a consistent ``.backup``-based copy of the live DB
  file. Safe to run while Streamlit is up; SQLite serializes the backup.

CLI::

    uv run python -m fitme.export csv [--to DIR] [--tables T1,T2] [--include-raw]
    uv run python -m fitme.export sqlite [--to FILE]
"""
from __future__ import annotations

import argparse
import csv
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fitme.config import load as load_settings
from fitme.db import connect
from fitme.logging_config import setup as setup_logging

logger = logging.getLogger(__name__)

SKIP_TABLES = frozenset({"schema_version", "sqlite_sequence"})


def _utc_stamp() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _user_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows if r[0] not in SKIP_TABLES]


def _table_columns(
    conn: sqlite3.Connection, table: str, *, include_raw: bool
) -> list[str]:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    cols = [r[1] for r in rows]
    if not include_raw:
        cols = [c for c in cols if c != "raw_json"]
    return cols


def table_row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Return ``{table: row_count}`` for every user table. Cheap full scan."""
    counts: dict[str, int] = {}
    for table in _user_tables(conn):
        row = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
        counts[table] = int(row[0])
    return counts


def export_csv(
    conn: sqlite3.Connection,
    out_dir: Path,
    *,
    tables: list[str] | None = None,
    include_raw: bool = False,
) -> list[Path]:
    """Dump one CSV per table under ``out_dir``. Returns paths written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    selected = tables or _user_tables(conn)
    written: list[Path] = []
    for table in selected:
        cols = _table_columns(conn, table, include_raw=include_raw)
        if not cols:
            logger.warning("Skipping %s: no exportable columns", table)
            continue
        path = out_dir / f"{table}.csv"
        quoted_cols = ", ".join(f'"{c}"' for c in cols)
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(cols)
            for row in conn.execute(f'SELECT {quoted_cols} FROM "{table}"'):
                writer.writerow(row)
        written.append(path)
        logger.info("Wrote %s (%d cols)", path, len(cols))
    return written


def export_sqlite(src_path: Path, dest_path: Path) -> None:
    """Atomic ``.backup`` copy of ``src_path`` to ``dest_path``.

    Uses SQLite's built-in backup API so the result is consistent even if
    other connections are writing to the source.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(src_path)
    try:
        dest = sqlite3.connect(dest_path)
        try:
            src.backup(dest)
        finally:
            dest.close()
    finally:
        src.close()
    logger.info("Wrote %s", dest_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _default_export_root() -> Path:
    return load_settings().db_path.parent / "exports"


def _parse_tables(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [t.strip() for t in value.split(",") if t.strip()]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fitme.export")
    sub = parser.add_subparsers(dest="format", required=True)

    csv_p = sub.add_parser("csv", help="Dump one CSV per table.")
    csv_p.add_argument(
        "--to",
        type=Path,
        help="Output directory. Default: data/exports/<utc-iso>/",
    )
    csv_p.add_argument(
        "--tables",
        type=str,
        help="Comma-separated subset (default: all user tables).",
    )
    csv_p.add_argument(
        "--include-raw",
        action="store_true",
        help="Include the raw_json columns (default: skip them).",
    )

    sqlite_p = sub.add_parser("sqlite", help="Atomic SQLite snapshot.")
    sqlite_p.add_argument(
        "--to",
        type=Path,
        help="Output file. Default: data/exports/fitme-<utc-iso>.db",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = _build_parser().parse_args(argv)
    stamp = _utc_stamp()
    root = _default_export_root()

    if args.format == "csv":
        out_dir = args.to or (root / stamp)
        tables = _parse_tables(args.tables)
        with connect() as conn:
            written = export_csv(
                conn, out_dir,
                tables=tables, include_raw=args.include_raw,
            )
        logger.info("CSV export complete: %d file(s) under %s", len(written), out_dir)
        return 0

    if args.format == "sqlite":
        src = load_settings().db_path
        dest = args.to or (root / f"fitme-{stamp}.db")
        export_sqlite(src, dest)
        logger.info("SQLite snapshot complete: %s", dest)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
