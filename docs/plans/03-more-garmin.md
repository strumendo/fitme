# Phase 3 — Expanded Garmin metrics

Status: not started
Last updated: 2026-05-10

## Goal

Cover the rest of what Garmin Connect exposes that's relevant to fitness
evolution: activities list, body battery, stress, HRV, sleep stages, body
composition. The dashboard becomes a full picture, not just steps + HR.

## Why now

- Persistence (Phase 1) and visualization (Phase 2) wiring is in place, so
  adding a metric is mechanical: API wrapper → schema migration → ingest
  function → chart.
- Doing this earlier would mean redoing the wiring multiple times.

## Scope

**In:**
- **Activities list** — type, start time, duration, distance, calories, avg
  HR per activity. The most useful new dimension.
- **Body battery** — daily series (Garmin's energy proxy).
- **Stress level** — daily and intra-day if available.
- **HRV** — overnight values (sensitive metric, worth tracking).
- **Sleep stages detail** — extend the existing `sleep` table with stage
  breakdown if not already there from Phase 1.
- **Body composition** — body fat %, muscle mass, etc. from the Garmin scale,
  if applicable (extend `weight` table).

**Out:**
- Editing / correcting Garmin data. Dashboard is read-only over Garmin-sourced
  rows.
- Workout-detail breakdowns (lap times, GPS traces) — possible later, but not
  this phase.
- Training Status / VO2max / training load — defer; they often need the full
  device sync and may not be on the API.

## Approach

### One pattern, repeated per metric

For each new metric:
1. **API wrapper** in `src/fitme/garmin.py` — thin function taking the
   `Garmin` client, returning the raw payload.
2. **Schema migration** — bump `SCHEMA_VERSION`, add a `migrate_vN(conn)` that
   creates the new table or adds the new columns.
3. **Ingest function** in `src/fitme/ingest.py` — fetch + upsert. Idempotent.
4. **Query helpers** in `src/fitme/queries.py` — `single_date` and `range`
   variants, returning dicts and DataFrames respectively.
5. **UI**:
   - "Today" page: a card / metric section.
   - "Trends" page: a chart section.
   - Activities only: a dedicated `pages/3_Activities.py` page (table + filters).

### Activities — schema sketch

```sql
CREATE TABLE activities (
    activity_id       INTEGER PRIMARY KEY,    -- Garmin id, stable
    date              TEXT NOT NULL,           -- start date in user TZ
    start_time        TEXT NOT NULL,           -- ISO datetime
    type              TEXT,                    -- running, cycling, strength, ...
    duration_s        INTEGER,
    distance_m        REAL,
    calories_kcal     REAL,
    avg_hr_bpm        INTEGER,
    max_hr_bpm        INTEGER,
    raw_json          TEXT,
    fetched_at        TEXT NOT NULL
);
CREATE INDEX activities_date_idx ON activities(date);
```

Ingest pulls the activities list endpoint (paged) and upserts each by
`activity_id`. The `date` column is denormalized from `start_time` so range
queries are simple joins to the daily tables.

### Body battery / stress / HRV

These are daily time series, ingest model is the same as `daily_summary` —
one row per date.

## Tasks

(Per metric, in order of value: Activities → Body battery → Stress → HRV →
Sleep stages → Body composition.)

For each metric:
1. Add API wrapper in `src/fitme/garmin.py`.
2. Add migration in `src/fitme/db_schema.py`.
3. Add ingest in `src/fitme/ingest.py`.
4. Add query helpers in `src/fitme/queries.py`.
5. Add UI: card on "Today", chart on "Trends" (and dedicated page for
   Activities).
6. Update root `CLAUDE.md`: list the new tables and helpers.

End of phase:
- Update this file's status to `done`.

## Acceptance

- [ ] Activities page lists recent activities with filtering by type and date
      range, and links each row to a detail expander showing the raw JSON.
- [ ] Body battery, stress and HRV appear as line charts on the Trends page
      with the same UX as Phase 2 metrics (rolling avg toggle, period delta).
- [ ] Body composition appears on the Today page when data exists for the
      selected date.
- [ ] `uv run python -m fitme.ingest --since 30d --metrics all` populates all
      tables introduced in this phase.

## Open questions

- Some metrics (HRV, body battery) may not be on the unofficial API or may
  require specific device support. Probe each in implementation; if missing,
  document the gap here and move on rather than blocking the phase.
- Activities pagination — confirm how `get_activities()` paginates and pick
  a sane default per-run cap.
- Should Activities live in its own page from day 1, or share Trends? Default:
  own page (`pages/3_Activities.py`) — its data shape is different.

## Cross-phase notes

- After this phase, schema_version is likely v3 or v4. Update the root
  `CLAUDE.md` "Data flow" / schema notes accordingly.
- Phase 4 (manual training log) will want to *match* manual sessions to
  Garmin `activities` rows. Keep that in mind when designing the activities
  table — `activity_id` as primary key (Garmin id) makes matching
  unambiguous.
