# Phase 1 — Local persistence (SQLite)

Status: done
Last updated: 2026-05-12

## Goal

Own a local copy of the Garmin data we care about, so the dashboard and every
later phase can read history without hitting the Garmin Connect API on every
view. The DB is the source of truth for the UI; live API calls happen only
during ingestion.

## Why now

- Garmin Connect's API is rate-limited and not always deep in history; we want
  retention independent of what Garmin exposes today.
- Phases 2–4 all assume historical data exists locally — they don't have to
  re-fetch from Garmin to render a chart.
- Establishes the "schema → ingest → query" pipeline once, so adding a new
  metric in Phase 3 is mechanical.

## Scope

**In:**
- SQLite database at `data/fitme.db` (path overridable via `FITME_DB_PATH`).
- Tables for daily summary, heart rate, sleep, weight (covers what Phase 2
  charts will need).
- An ingest CLI: `uv run python -m fitme.ingest --since 30d` (also accepts
  `--from YYYY-MM-DD --to YYYY-MM-DD`).
- Idempotent ingestion (`INSERT OR REPLACE` keyed by date / activity id).
- Hand-written schema migrations applied on every connect — no Alembic.
- Dashboard reads from the DB. If the selected date has no row, optionally
  falls back to a live Garmin call (behind a setting; off by default to keep
  the UI fast).

**Out:**
- ORMs (SQLAlchemy, SQLModel) — overkill for one user and stdlib `sqlite3` is
  fine here.
- Scheduled / automated ingestion (systemd timer, cron, GitHub Actions).
  Manual run for now; a wrapper script can be added later.
- Activities table (Phase 3 — its shape is messier).
- Multi-user / remote DB.

## Approach

### Module layout

```
src/fitme/
  db.py             # connect(), context manager, applies migrations on open
  db_schema.py      # SCHEMA_VERSION + migrate(conn) — hand-written SQL
  ingest.py         # CLI entry point + per-metric ingest_* functions
  queries.py        # NEW — read-side helpers returning dicts/DataFrames
data/               # gitignored, created on first run
  fitme.db
```

### Schema (v1)

All dates are `TEXT` ISO `YYYY-MM-DD` for simplicity and human-readability.

```sql
CREATE TABLE schema_version (version INTEGER NOT NULL);

CREATE TABLE daily_summary (
    date              TEXT PRIMARY KEY,
    steps             INTEGER,
    distance_m        REAL,
    calories_kcal     REAL,
    active_minutes    INTEGER,
    floors_climbed    INTEGER,
    raw_json          TEXT,                -- full payload for forward compat
    fetched_at        TEXT NOT NULL
);

CREATE TABLE heart_rate (
    date              TEXT PRIMARY KEY,
    resting_bpm       INTEGER,
    max_bpm           INTEGER,
    min_bpm           INTEGER,
    avg_bpm           INTEGER,
    raw_json          TEXT,
    fetched_at        TEXT NOT NULL
);

CREATE TABLE sleep (
    date              TEXT PRIMARY KEY,
    total_seconds     INTEGER,
    deep_seconds      INTEGER,
    light_seconds     INTEGER,
    rem_seconds       INTEGER,
    awake_seconds     INTEGER,
    raw_json          TEXT,
    fetched_at        TEXT NOT NULL
);

CREATE TABLE weight (
    date              TEXT PRIMARY KEY,    -- one effective weight per day
    weight_kg         REAL,
    body_fat_pct      REAL,
    body_water_pct    REAL,
    muscle_mass_kg    REAL,
    bone_mass_kg      REAL,
    raw_json          TEXT,
    fetched_at        TEXT NOT NULL
);
```

`raw_json` keeps the full Garmin payload so we can backfill new columns from
existing rows when the schema grows, without re-hitting the API.

### Migration strategy

`db_schema.py` exposes `SCHEMA_VERSION` and a `migrate(conn)` function. On
every `db.connect()` we read `schema_version`, compare, and apply the missing
forward migrations sequentially. Each migration is a Python function taking a
connection. No down-migrations.

### Ingest

`fitme.ingest` is both a module (importable functions) and a CLI:

```bash
uv run python -m fitme.ingest --since 30d
uv run python -m fitme.ingest --from 2026-04-01 --to 2026-04-30
uv run python -m fitme.ingest --date 2026-05-10            # single day
uv run python -m fitme.ingest --metrics summary,sleep      # subset
```

Per metric, one function: `ingest_daily_summary(client, conn, day)` that
fetches, parses, and upserts. The CLI iterates dates × selected metrics. Logs
progress via `logger.info`, errors via `logger.exception`, never `print`.

### Dashboard integration

`app.py`:
- Reads via `fitme.queries.get_daily_summary(conn, date)` and friends.
- If a date is empty in the DB, shows an info banner with a button:
  "Fetch from Garmin for 2026-05-10" → calls the ingest function for that
  date and reruns.

## Tasks

1. Add `src/fitme/db.py` (connect, context manager, applies migrations).
2. Add `src/fitme/db_schema.py` (`SCHEMA_VERSION = 1`, `migrate()`).
3. Add `src/fitme/queries.py` (read helpers per table).
4. Add `src/fitme/ingest.py` with the per-metric ingest functions and a CLI.
5. Wire `FITME_DB_PATH` (default `data/fitme.db`) into `config.py` and
   `.env.example`.
6. Add `data/` to `.gitignore`.
7. Switch `app.py` to read from `queries`, with the empty-day fallback UI.
8. Update root `CLAUDE.md`: new modules in Layout, new commands, new env var,
   note that the dashboard reads from the DB and ingest is manual.
9. Update this file's status to `done` once Acceptance is met.

## Acceptance

- [ ] `uv run python -m fitme.ingest --since 7d` populates four tables with the
      last 7 days where data exists, with sensible logging.
- [ ] Running the same command again does not create duplicates.
- [ ] `data/fitme.db` is created automatically on first run and never committed.
- [ ] Streamlit dashboard renders the same numbers as before for today, but the
      page load makes zero outbound calls when the DB has the data.
- [ ] Opening a date that has no row shows the "fetch from Garmin" banner and
      the button populates that date.

## Open questions

- **Activities ingestion** — defer entirely to Phase 3, or pull a thin
  `activities(id, date, type, duration_s, distance_m, calories)` already in
  Phase 1 so charts can show activity counts? Default for now: defer.
- **Backfill depth on first run** — 30 days? 90? Probably surface as a flag
  rather than picking a default.
- **Timezone** — Garmin returns dates already in the user's TZ. Confirm during
  implementation; if not, normalise at ingest time.

## Cross-phase notes

- The `raw_json` column is the contract with later phases: any new field they
  need can be derived from stored JSON until the schema grows a typed column.
- `queries.py` will be reused heavily in Phase 2 (it's already in the layout
  for that reason).
