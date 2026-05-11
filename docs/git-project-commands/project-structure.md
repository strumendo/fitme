# GitHub Project — fitme Roadmap

Blueprint for a GitHub Projects (v2) board that mirrors the roadmap under
[`docs/plans/`](../plans/README.md). One epic per phase, one task per item in
each phase's **Tasks** section. Milestones group epics; labels enable filtering.

The companion file [`setup-commands.md`](setup-commands.md) contains the `gh` CLI
commands that materialize this structure in `github.com/strumendo/fitme`.

## Project

| Field | Value |
| --- | --- |
| Name | `fitme Roadmap` |
| Owner | `@me` (user-level project) |
| Description | Personal roadmap for the fitme dashboard — mirrors `docs/plans/`. |
| Default views | `Board` grouped by `Status`, `Table` grouped by `Milestone` |

Custom fields to add after creation (via the web UI — `gh` v2.45 only supports
basic field types from the CLI):

- `Status` — default field (`Todo`, `In progress`, `Done`).
- `Phase` — single-select: `1 · Persistence`, `2 · Time series`, `3 · Garmin metrics`, `4 · Manual inputs`.
- `Type` — single-select: `Epic`, `Task`.

## Labels

| Label | Color | Purpose |
| --- | --- | --- |
| `type:epic` | `B60205` | Marks an issue that tracks a whole phase. |
| `type:task` | `0E8A16` | Marks a concrete, mergeable unit of work. |
| `phase:1` | `1D76DB` | Belongs to Phase 1 — Persistence. |
| `phase:2` | `5319E7` | Belongs to Phase 2 — Time series. |
| `phase:3` | `D93F0B` | Belongs to Phase 3 — Garmin metrics. |
| `phase:4` | `FBCA04` | Belongs to Phase 4 — Manual inputs. |
| `area:db` | `C5DEF5` | Schema, migrations, SQLite layer. |
| `area:ingest` | `BFD4F2` | Garmin → DB ingestion pipeline. |
| `area:ui` | `D4C5F9` | Streamlit pages and forms. |
| `area:garmin` | `F9D0C4` | `fitme.garmin` wrappers / Garmin API. |
| `area:docs` | `FEF2C0` | `CLAUDE.md`, plan files, READMEs. |

## Milestones

One per phase. No due dates — pace is dictated by life, not deadlines.

| Milestone | Description |
| --- | --- |
| `Phase 1 — Persistence` | SQLite local DB + ingest CLI. See `docs/plans/01-persistence.md`. |
| `Phase 2 — Time series` | Multi-page dashboard with range charts. See `docs/plans/02-time-series.md`. |
| `Phase 3 — Garmin metrics` | Activities, body battery, stress, HRV, sleep stages, body comp. See `docs/plans/03-more-garmin.md`. |
| `Phase 4 — Manual inputs` | Training plan, training log, food log. See `docs/plans/04-manual-inputs.md`. |

## Phase 1 — Persistence

**Epic:** `[Epic] Phase 1 — Local persistence (SQLite)`
Labels: `type:epic`, `phase:1`, `area:db`
Milestone: `Phase 1 — Persistence`

Tasks (each gets its own issue):

| # | Title | Labels |
| --- | --- | --- |
| 1.1 | Add `src/fitme/db.py` — connect, context manager, applies migrations on open | `type:task`, `phase:1`, `area:db` |
| 1.2 | Add `src/fitme/db_schema.py` — `SCHEMA_VERSION = 1` and `migrate(conn)` | `type:task`, `phase:1`, `area:db` |
| 1.3 | Add `src/fitme/queries.py` — read helpers per table | `type:task`, `phase:1`, `area:db` |
| 1.4 | Add `src/fitme/ingest.py` — per-metric ingest functions and CLI | `type:task`, `phase:1`, `area:ingest` |
| 1.5 | Wire `FITME_DB_PATH` into `config.py` and `.env.example` | `type:task`, `phase:1`, `area:db` |
| 1.6 | Add `data/` to `.gitignore` | `type:task`, `phase:1`, `area:db` |
| 1.7 | Switch `app.py` to read from `queries` with empty-day fallback UI | `type:task`, `phase:1`, `area:ui` |
| 1.8 | Update root `CLAUDE.md` — new modules, commands, env var, data flow | `type:task`, `phase:1`, `area:docs` |

## Phase 2 — Time series

**Epic:** `[Epic] Phase 2 — Time series + history view`
Labels: `type:epic`, `phase:2`, `area:ui`
Milestone: `Phase 2 — Time series`

| # | Title | Labels |
| --- | --- | --- |
| 2.1 | Migrate `app.py` to "Today" landing page | `type:task`, `phase:2`, `area:ui` |
| 2.2 | Add `pages/2_Trends.py` — range picker + 7/30/90d quick buttons | `type:task`, `phase:2`, `area:ui` |
| 2.3 | Extend `fitme/queries.py` with `*_range` helpers (DataFrames) | `type:task`, `phase:2`, `area:db` |
| 2.4 | Add `fitme/analysis.py` — `rolling()` and `period_delta()` | `type:task`, `phase:2`, `area:ui` |
| 2.5 | Build per-metric chart sections (steps, HR, sleep, weight, calories, active min) | `type:task`, `phase:2`, `area:ui` |
| 2.6 | Update root `CLAUDE.md` — multi-page layout, new modules, chart recipe | `type:task`, `phase:2`, `area:docs` |

## Phase 3 — Garmin metrics

**Epic:** `[Epic] Phase 3 — Expanded Garmin metrics`
Labels: `type:epic`, `phase:3`, `area:garmin`
Milestone: `Phase 3 — Garmin metrics`

One task per metric, each following the pattern: API wrapper → migration →
ingest → queries → UI.

| # | Title | Labels |
| --- | --- | --- |
| 3.1 | Activities — wrapper, `activities` table, ingest, queries, `pages/3_Activities.py` | `type:task`, `phase:3`, `area:garmin` |
| 3.2 | Body battery — wrapper, table, ingest, queries, Trends chart | `type:task`, `phase:3`, `area:garmin` |
| 3.3 | Stress level — wrapper, table, ingest, queries, Trends chart | `type:task`, `phase:3`, `area:garmin` |
| 3.4 | HRV — wrapper, table, ingest, queries, Trends chart | `type:task`, `phase:3`, `area:garmin` |
| 3.5 | Sleep stages — extend `sleep` table, ingest stage breakdown, UI | `type:task`, `phase:3`, `area:garmin` |
| 3.6 | Body composition — extend `weight` table, ingest, Today card | `type:task`, `phase:3`, `area:garmin` |
| 3.7 | Update root `CLAUDE.md` — new tables, helpers, schema_version bump | `type:task`, `phase:3`, `area:docs` |

## Phase 4 — Manual inputs

**Epic:** `[Epic] Phase 4 — Manual inputs: training routine + food log`
Labels: `type:epic`, `phase:4`, `area:ui`
Milestone: `Phase 4 — Manual inputs`

| # | Title | Labels |
| --- | --- | --- |
| 4.1 | Schema migration — `training_plan`, `training_log`, `food_log` tables | `type:task`, `phase:4`, `area:db` |
| 4.2 | Add `src/fitme/repository.py` — CRUD for plan / log / food | `type:task`, `phase:4`, `area:db` |
| 4.3 | Extend `fitme/queries.py` — `plan_for_date`, `training_log_range`, `food_log_range`, `food_macros_summary` | `type:task`, `phase:4`, `area:db` |
| 4.4 | Build `pages/4_Training.py` — plan editor, log form, plan-vs-actual view | `type:task`, `phase:4`, `area:ui` |
| 4.5 | Build `pages/5_Food.py` — entry form, per-day totals, range macro trends | `type:task`, `phase:4`, `area:ui` |
| 4.6 | Extend `app.py` "Today" — planned training + logged training + food totals | `type:task`, `phase:4`, `area:ui` |
| 4.7 | Edit/delete UIs for all manual entries | `type:task`, `phase:4`, `area:ui` |
| 4.8 | Update root `CLAUDE.md` — new tables, pages, `repository.py`, plan-vs-actual UX | `type:task`, `phase:4`, `area:docs` |

## Epic ↔ task linking

Each epic's body contains a markdown task list referencing its child issues:

```markdown
## Tasks
- [ ] #12 Add `src/fitme/db.py` — connect, context manager, applies migrations
- [ ] #13 Add `src/fitme/db_schema.py` — SCHEMA_VERSION + migrate()
...
```

GitHub turns `- [ ] #N` into a tracked sub-issue automatically, so closing a
task ticks its box on the epic. The setup script captures task issue numbers
first, then writes the epic body referencing them.
