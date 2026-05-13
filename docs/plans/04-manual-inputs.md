# Phase 4 — Manual inputs: training routine + food log

Status: in progress
Last updated: 2026-05-13

## Goal

Close the loop on the README's promise: "Garmin + routine training + food".
Capture the planned weekly training routine, log actual sessions, and record
the daily food log — all alongside the Garmin-sourced data already in the DB.

## Why now

- Touches both DB schema (new tables, references to dates / activity ids) and
  UI (forms, edit/delete, validation). Easier to layer on a mature skeleton
  than to retrofit later.
- Phase 3 added an `activities` table — manual training logs can be matched
  against it for "planned vs actual" views.

## Scope

**In:**
- **Training plan** — a recurring weekly template (e.g., Mon = lower body,
  Wed = run, Sat = long ride). One row per (week-day × slot), versioned by
  effective date so changes don't rewrite history.
- **Training log** — actual sessions, manually entered, optionally matched to
  a Garmin `activity_id`. Includes type, duration, perceived effort (1–10),
  notes.
- **Food log** — per-meal entries with kcal + macros (protein/carbs/fat) and
  free-text notes. No external nutrient DB lookup in this phase.
- **Daily view** — the "Today" page extends to show: Garmin metrics + planned
  training for today + actual training + food entries.
- **Edit / delete** from the UI for any manual entry.

**Out:**
- Full nutrient database (USDA, Open Food Facts) lookups. Manual macros for
  now; revisit as a Phase 5 if useful.
- Workout programming detail (sets × reps × load per exercise). Start with a
  single-row session; expand only if the data is being used.
- Calendar UI / drag-and-drop scheduling.
- Multi-user notion of "shared plans".

## Approach

### Schema

```sql
CREATE TABLE training_plan (
    plan_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    effective_from    TEXT NOT NULL,    -- ISO date when this version starts
    weekday           INTEGER NOT NULL, -- 0=Mon … 6=Sun
    slot              INTEGER NOT NULL DEFAULT 0, -- multiple sessions/day
    activity_type     TEXT NOT NULL,    -- e.g. 'run', 'strength_lower'
    description       TEXT,
    target_duration_min INTEGER,
    UNIQUE(effective_from, weekday, slot)
);

CREATE TABLE training_log (
    log_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date              TEXT NOT NULL,
    activity_type     TEXT NOT NULL,
    duration_min      INTEGER,
    perceived_effort  INTEGER,          -- 1..10
    notes             TEXT,
    garmin_activity_id INTEGER,         -- FK-style ref to activities(activity_id)
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
CREATE INDEX training_log_date_idx ON training_log(date);

CREATE TABLE food_log (
    food_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    date              TEXT NOT NULL,
    meal              TEXT,             -- breakfast/lunch/dinner/snack (free text ok)
    description       TEXT NOT NULL,
    kcal              REAL,
    protein_g         REAL,
    carbs_g           REAL,
    fat_g             REAL,
    notes             TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
CREATE INDEX food_log_date_idx ON food_log(date);
```

`training_plan` is versioned by `effective_from`: when the user changes the
weekly template, insert new rows with a new `effective_from`; old rows stay so
history is reproducible. `current_plan_for(date)` returns the rows where
`effective_from <= date` is the latest such date.

### Pages

```
app.py                       # "Today" — extend with sections for plan/log/food
pages/
  2_Trends.py                # from Phase 2
  3_Activities.py            # from Phase 3
  4_Training.py              # plan editor + log entry + plan vs actual view
  5_Food.py                  # food log entry + per-day totals + macro split
```

### Plan vs actual matching

For each day, surface:
- Planned slots from `training_plan` effective on that date.
- Logged sessions from `training_log` for that date.
- Garmin activities from `activities` for that date.

A logged session can be linked to a Garmin activity via `garmin_activity_id`
(dropdown in the form, populated from same-day activities). When linked, the
duration and type from Garmin can prefill the log entry.

### Forms

Use `st.form` so submission is atomic. Validate on submit; surface errors via
`st.error`. Persist via small functions in `fitme/repository.py` (a thin
module added in this phase to keep mutation logic out of pages).

## Tasks

1. Schema migration for the three tables (bump `SCHEMA_VERSION`).
2. Add `src/fitme/repository.py` — CRUD for plan, log, food.
3. Extend `src/fitme/queries.py` — `plan_for_date`, `training_log_range`,
   `food_log_range`, `food_macros_summary`.
4. Build `pages/4_Training.py`:
   - "Weekly plan" editor (add / edit / supersede rows).
   - "Log a session" form (with optional Garmin activity link).
   - "Plan vs actual" view for a date range.
5. Build `pages/5_Food.py`:
   - "Add entry" form per meal.
   - Per-day totals (kcal + macro pie/bar).
   - Per-range trends (avg kcal/day, macro split).
6. Extend `app.py` "Today" page to show: today's planned training, logged
   training, and food totals next to the Garmin block.
7. Edit/delete UIs (or just edit-in-place tables) for log entries.
8. Update root `CLAUDE.md`: new tables, new pages, `repository.py` location,
   the plan-vs-actual UX summary.
9. Update this file's status to `done` once Acceptance is met.

## Acceptance

- [ ] User can set up a weekly training plan from the UI and supersede it
      later without losing history.
- [ ] User can log an actual training session and optionally link it to a
      Garmin activity from that day.
- [ ] User can add food entries with kcal + macros and see per-day totals and
      a range view of average daily intake.
- [ ] "Today" page shows: Garmin block + planned training for today +
      actual training logged today + food log totals for today.
- [ ] Edit and delete work for all manual entries.

## Open questions

- Plan granularity — single session per day or multiple slots (AM / PM)?
  Schema supports `slot`; UI will start with single-slot to keep it simple
  and expand if needed.
- Nutrient DB — should we wire Open Food Facts now or stay manual? Default:
  stay manual in this phase; the macro fields are already in the schema, so
  a later phase can layer a lookup without migration.
- "Adherence" metric (planned vs done %) — nice-to-have; include if it falls
  out cleanly from the plan-vs-actual view, otherwise defer.

## Cross-phase notes

- After this phase, the dashboard is the README's full vision: Garmin +
  routine + food in one place.
- Backup/export of the manual data becomes more important once it's been
  curated by hand. Consider a Phase 5 plan for "export to CSV / backup
  fitme.db".
