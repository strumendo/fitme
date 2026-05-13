# Phase 5 — Export & backup of fitme.db

Status: done
Last updated: 2026-05-13

## Goal

Give the dashboard a one-command (and one-click) way to dump the SQLite DB
to portable formats and to take a consistent snapshot. Phase 4 added
hand-curated data (training plan, training log, food log) that doesn't come
from Garmin — losing it would mean re-typing weeks of entries. Today the
only "backup" is copying `data/fitme.db` manually.

## Why now

- Phase 4 introduced data that **cannot be re-ingested** from Garmin.
  Backup matters more once data is irreplaceable.
- Cheap to build — no schema, no external API, no new dependencies.
- Future phases (Open Food Facts lookup, workout detail) will reshape
  tables; having a checked-in backup path lets us migrate without fear.

## Scope

**In:**
- **CLI** `python -m fitme.export` with two subcommands:
  - `csv` — one CSV per table under a timestamped directory.
  - `sqlite` — consistent snapshot via SQLite's `.backup` (not a `cp`).
- **Output defaults** — under `data/exports/<UTC-ISO-timestamp>/` (CSV) or
  `data/exports/<UTC-ISO-timestamp>.db` (SQLite). Overridable with `--to`.
- **Filtering flags**:
  - `--tables daily_summary,sleep,...` to dump a subset (default: all).
  - `--include-raw` to keep the `raw_json` columns (default: skip them — they
    balloon CSV size for little value outside debugging).
- **Streamlit UI** — a dedicated `pages/9_Backup.py` page with:
  - "Download SQLite snapshot" button → bytes of a fresh `.backup` served
    via `st.download_button`.
  - "Download CSV bundle" button → in-memory ZIP of the same CSV dumps,
    served via `st.download_button`.

**Out:**
- **Restore / import.** One-way only in this phase. Restoring is currently
  "stop Streamlit, replace `data/fitme.db`, restart" — good enough for now.
- **JSON dump format.** Skipped — CSV covers the spreadsheet/portability
  case; SQLite covers the fidelity case.
- **Scheduled backups / cloud upload.** Out of scope; the user can wire
  `cron` against the CLI if desired.
- **Encryption / password protection.** No.
- **Selective row export** (date ranges, etc.). Whole-table only.

## Approach

### New module `src/fitme/export.py`

Owns the export logic. Reads via `db.connect()`. Two public entry points:

- `export_csv(conn, out_dir: Path, *, tables: list[str] | None, include_raw: bool) -> list[Path]`
  - Lists tables from `sqlite_master` (skip `schema_version` and
    `sqlite_sequence`).
  - For each table, fetches column names from `PRAGMA table_info`, filters
    out `raw_json` if `include_raw` is False.
  - Writes `<out_dir>/<table>.csv` using stdlib `csv.writer`. Header row =
    selected columns.
  - Returns the list of files written (the page can use this to build a ZIP).
- `export_sqlite(src_path: Path, dest_path: Path) -> None`
  - Opens both connections, calls `src.backup(dest)` — atomic, consistent
    even under concurrent writes.

### CLI `python -m fitme.export`

```
python -m fitme.export csv [--to DIR] [--tables T1,T2] [--include-raw]
python -m fitme.export sqlite [--to FILE]
```

- Uses `argparse` with subparsers — mirrors `ingest.py` style.
- Default `--to` resolves to `data/exports/<utc-iso>/` or `.db`. Creates
  parent dirs.
- Logs each file written via `logger.info` (no `print`).

### UI `pages/9_Backup.py`

- Two big buttons (`st.download_button`) — SQLite snapshot bytes, CSV
  bundle (built in-memory as a `BytesIO` with `zipfile.ZipFile`).
- Counts row counts per table on render (cheap query) so the user knows
  what's about to be exported.
- `st.caption` next to each button with the suggested filename
  (`fitme-<utc-iso>.db`, `fitme-<utc-iso>.zip`).

### Where exports live

- CLI default writes into `data/exports/` — gitignored alongside `data/`.
- The UI downloads stream bytes directly to the browser; nothing persists
  server-side (avoids cleanup later).

## Tasks

1. Add `src/fitme/export.py` with `export_csv` + `export_sqlite`.
2. Wire CLI `python -m fitme.export` with `csv` / `sqlite` subcommands.
3. Add `pages/9_Backup.py` with the two download buttons + per-table row
   counts.
4. Update `src/fitme/CLAUDE.md` — new module, new CLI command row.
5. Update `pages/CLAUDE.md` — new page in the layout block.
6. Confirm `data/exports/` is covered by the existing `data/` gitignore
   entry (it is — same prefix).
7. Update this file's status to `done` once Acceptance is met.

## Acceptance

- [x] `python -m fitme.export csv` produces one CSV per table under a
      timestamped directory; re-runs don't clobber prior exports.
- [x] `python -m fitme.export sqlite` produces a working SQLite file —
      `sqlite3 <file> "SELECT COUNT(*) FROM daily_summary;"` returns the
      same row count as the source.
- [x] `--include-raw` flag toggles the `raw_json` columns; default skips
      them.
- [x] Backup page in Streamlit downloads both formats; row counts shown
      match the source DB.
- [x] No regressions in existing pages (ruff clean; streamlit boots).

## Open questions

- **CSV dialect** — default Python (`,` separator, `\r\n` line ending) or
  Excel-friendly (`;` separator, UTF-8 BOM)? Default: Python defaults; can
  add a `--dialect` flag later if pasting into a sheet gets annoying.
- **Activities `raw_json` size** — by default we strip it, but if someone
  wants a full reproducible dump (e.g., to re-derive metrics offline), the
  flag is there. Worth documenting in the page UI.
- **Timestamp granularity in filenames** — second precision (`20260513T143000Z`)
  should be enough. If we hit the same-second collision case, we can switch
  to ms later.

## Cross-phase notes

- Future "import / restore" can layer on top of the same `export.py`
  module — a `restore_sqlite(src, dest)` would mirror `export_sqlite`.
- If the Open Food Facts phase adds a `food_cache` table, the export
  automatically picks it up (no hardcoded table list).
