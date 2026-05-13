# Phase 7 — Workout detail: sets × reps × load

Status: in progress
Last updated: 2026-05-13

## Goal

Stop logging strength training as a single line ("strength_lower, 45 min,
effort 7"). Capture each working set — exercise, weight, reps, optional
RPE — so progression over time can actually be measured. Add a small
analytics page that shows load history for a chosen exercise.

## Why now

- Phase 4 left this open: the training_log captures duration + effort but
  not the actual stimulus. After a couple of months using the planner,
  the missing detail is what makes lift progress invisible in the
  dashboard.
- Phase 5 (backup) and phase 6 (OFF lookup) didn't touch `training_log`,
  so the schema is still simple enough to extend cleanly.
- Exercise data is the last big gap before the dashboard covers the
  README's promise end-to-end with useful granularity.

## Scope

**In:**
- **Schema v4** — one new table `exercise_set`, FK-style ref to
  `training_log.log_id`. Free-text `exercise_name` (canonicalization
  deferred — see Open questions).
- **Repository helpers** — insert / update / delete for `exercise_set`,
  consistent with the existing `repository.py` pattern.
- **Queries** — `exercise_set_for_log(log_id)`,
  `exercise_names(start, end)` for autocomplete suggestions,
  `exercise_history(name, start, end)` for the analytics page.
- **Training page extension** (`pages/4_Training.py`) — each logged
  session in the plan-vs-actual view gets a "Sets" sub-section: a small
  table of existing sets with per-row delete, and a one-line form to add
  a new set (exercise, weight, reps, optional RPE).
- **Strength analytics page** (`pages/8_Strength.py`) — pick an exercise
  from a dropdown (distinct names from the chosen range) → see:
  - Time series of max weight per session and total volume (weight × reps × sets).
  - Estimated 1RM via Epley (`weight × (1 + reps/30)`) — useful when reps
    vary across sessions.
  - Recent sets table for the chosen exercise.

**Out:**
- **Exercise canonical table** with muscle groups, equipment, etc. Stay
  with free-text + distinct-name suggestion for now; revisit when the
  raw data shows the duplicate-naming pain.
- **Programmed templates** (e.g., "5x5 squat at 85%"). Logging only, no
  prescription beyond what `training_plan` already covers at the slot
  level.
- **Rest timers, supersets, tempo notation.** Way too much for v1.
- **Editing a set in place.** Use delete + re-add — same trade-off as
  the food entries were before phase 4 added inline edit.
- **PR computation** (all-time best per exercise). Easy to add later
  once the data is there; not in this phase to keep scope tight.

## Approach

### Schema (migration v4)

```sql
CREATE TABLE exercise_set (
    set_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    log_id         INTEGER NOT NULL,
    exercise_name  TEXT NOT NULL,
    set_number     INTEGER NOT NULL,
    weight_kg      REAL,
    reps           INTEGER,
    rpe            REAL,
    notes          TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE INDEX exercise_set_log_idx  ON exercise_set(log_id);
CREATE INDEX exercise_set_name_idx ON exercise_set(exercise_name);
```

- `log_id` is a logical reference to `training_log.log_id`; no formal
  FK declared (mirrors the rest of the schema — no `FOREIGN KEY` clauses
  anywhere else).
- `set_number` is computed at insert: next number for
  `(log_id, exercise_name)`. Lets the page show "Set 1, Set 2…" without
  the user having to track.
- `weight_kg` and `reps` are nullable so bodyweight / warm-up rows still
  fit. `rpe` is REAL 1.0–10.0 (half steps allowed).

### Repository (`src/fitme/repository.py`)

```python
def insert_exercise_set(conn, *, log_id, exercise_name, weight_kg=None,
                        reps=None, rpe=None, notes=None) -> int: ...
def delete_exercise_set(conn, set_id) -> None: ...
```

`set_number` is derived inside `insert_exercise_set`:

```sql
SELECT COALESCE(MAX(set_number), 0) + 1
FROM exercise_set
WHERE log_id = ? AND exercise_name = ?
```

No update helper in this phase (delete + re-add).

### Queries (`src/fitme/queries.py`)

- `exercise_set_for_log(log_id) -> list[dict]` — ordered by
  `(exercise_name, set_number)`.
- `exercise_names(start, end) -> list[str]` — distinct names from sets
  whose parent `training_log.date` falls in the range. Joins
  `exercise_set` and `training_log` on `log_id`.
- `exercise_history(name, start, end) -> list[dict]` — one row per set
  with the parent date alongside, ordered by date asc + set_number asc.

### Training page extension (`pages/4_Training.py`)

Inside each logged session's expander (in the plan-vs-actual view),
under the existing edit form, add a **"Sets"** block:

- Existing sets render as a small `st.dataframe` (read-only) plus a
  per-row "Delete" `st.button` keyed by `set_id`.
- "Add set" form (`st.form` for atomic submit): exercise name
  (`st.selectbox` with the distinct names from the last 90 days as
  options + free-text override), weight (kg), reps, RPE (slider 1–10
  with 0.5 step). Submitting calls `repository.insert_exercise_set`
  + `st.rerun`.

Empty state: when no sets exist for a session, just show the add form
with a caption.

### Strength analytics page (`pages/8_Strength.py`)

Mirrors the structure of `2_Trends.py` for familiarity:

- Range picker (7/30/90d quick + free pick).
- Exercise dropdown — `queries.exercise_names(start, end)`. If empty:
  caption "No sets logged in this range" + stop.
- Per-session aggregates via pandas: max weight, total volume
  (`weight × reps × sets`), estimated 1RM (Epley) per session.
- Three charts:
  - Line chart of max weight per session.
  - Line chart of total volume per session.
  - Line chart of estimated 1RM per session.
- Below the charts: recent sets table for that exercise (date, set,
  weight, reps, RPE) — last ~30 rows in range.

## Tasks

1. Migration v4 — `exercise_set` table + two indexes; bump
   `SCHEMA_VERSION` to 4 and register `_migrate_v4`.
2. Extend `src/fitme/repository.py` — `insert_exercise_set`
   (auto-numbered) + `delete_exercise_set`.
3. Extend `src/fitme/queries.py` — `exercise_set_for_log`,
   `exercise_names`, `exercise_history`.
4. Extend `pages/4_Training.py` — Sets block inside each logged session
   expander (list + per-row delete + add-set form with autocomplete).
5. New `pages/8_Strength.py` — range picker + exercise dropdown + three
   charts + recent-sets table.
6. Update `src/fitme/CLAUDE.md` — schema v4, new table row,
   repository/queries notes.
7. Update `pages/CLAUDE.md` — `8_Strength.py` listed; mention sets block
   under the food/training write-page pattern.
8. Update `app.py` docstring with the new page.
9. Mark this plan `done` once Acceptance is met.

## Acceptance

- [ ] Migration v4 applies cleanly on an existing DB (idempotent).
- [ ] Logging a strength session, then adding three sets of "Bench Press"
      with different weights/reps, persists them with set_numbers 1, 2, 3.
- [ ] Adding sets for a second exercise within the same session restarts
      set_numbers at 1 for that exercise.
- [ ] Delete on a set row removes it from the DB and the table.
- [ ] `8_Strength.py` shows the three charts and the recent-sets table
      for a chosen exercise over the last 30 days.
- [ ] No regressions in existing pages (`ruff check` clean; `streamlit
      run app.py` boots cleanly).

## Open questions

- **Canonical exercise names.** Free-text now (with last-90d
  autocomplete). If the duplicate-naming pain appears within a few weeks,
  introduce an `exercise` table in a follow-up phase and migrate
  `exercise_set` to reference it by id.
- **Bodyweight vs loaded.** `weight_kg = NULL` (or 0) means bodyweight.
  Volume calculation skips rows without weight. Could add a
  `bodyweight_kg` snapshot later if needed.
- **Linking to Garmin activities.** The session already has
  `garmin_activity_id`. Sets attach to the session, not directly to the
  Garmin activity — no extra wiring needed.
- **Per-exercise PRs (max weight, max reps@weight).** Trivial query, but
  better as a phase 8 once we know which "PR" definitions matter in
  practice.

## Cross-phase notes

- The export pipeline (phase 5) picks up the new table automatically
  thanks to its `sqlite_master`-based discovery — re-running
  `python -m fitme.export csv` will dump `exercise_set.csv` without code
  changes.
- The Today page (`app.py`) doesn't change in this phase — set-level
  detail lives inside the session expander on the Training page, not on
  the landing.
