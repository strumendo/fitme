# Setup commands — bootstrap the GitHub Project

End-to-end terminal recipe to materialize the structure described in
[`project-structure.md`](project-structure.md) inside
`github.com/strumendo/fitme`. Each section explains what it does, then gives
the commands. Run sections in order — later sections reference variables from
earlier ones, so keep the same shell session.

> The whole flow is also bundled as [`setup-commands.sh`](setup-commands.sh).
> Either run that script in one go, or copy each section below into the
> terminal as you read.

## 0. Prerequisites

- `gh` CLI installed and authenticated as `strumendo` (`gh auth status` confirms).
- Current working directory is the repo root (`/home/strumendo/PycharmProjects/fitme`).
- `jq` available for parsing JSON output (`sudo apt install jq` if missing).

```bash
gh auth status
gh repo view --json nameWithOwner -q .nameWithOwner   # must print strumendo/fitme
command -v jq >/dev/null || echo "install jq first"
```

## 1. Create labels

Labels enable filtering by type (`epic` / `task`), phase, and area. Re-running
the block is safe — `gh label create --force` updates existing labels in place.

```bash
# type:* — what the issue represents
gh label create "type:epic" --color B60205 --description "Tracks a whole phase" --force
gh label create "type:task" --color 0E8A16 --description "Concrete, mergeable unit of work" --force

# phase:* — which roadmap phase the issue belongs to
gh label create "phase:1" --color 1D76DB --description "Phase 1 — Persistence" --force
gh label create "phase:2" --color 5319E7 --description "Phase 2 — Time series" --force
gh label create "phase:3" --color D93F0B --description "Phase 3 — Garmin metrics" --force
gh label create "phase:4" --color FBCA04 --description "Phase 4 — Manual inputs" --force

# area:* — which part of the codebase the issue touches
gh label create "area:db"      --color C5DEF5 --description "Schema, migrations, SQLite"    --force
gh label create "area:ingest"  --color BFD4F2 --description "Garmin → DB ingestion"          --force
gh label create "area:ui"      --color D4C5F9 --description "Streamlit pages and forms"      --force
gh label create "area:garmin"  --color F9D0C4 --description "fitme.garmin / Garmin API"      --force
gh label create "area:docs"    --color FEF2C0 --description "CLAUDE.md, plans, READMEs"      --force
```

## 2. Create milestones

`gh` has no top-level `milestone` command, so we POST to the REST API. Output
is captured into shell variables holding each milestone's number; the issue
creation step below needs the **title** (not the number) via `--milestone`.

```bash
gh api repos/strumendo/fitme/milestones -f title="Phase 1 — Persistence" \
  -f description="SQLite local DB + ingest CLI. See docs/plans/01-persistence.md."
gh api repos/strumendo/fitme/milestones -f title="Phase 2 — Time series" \
  -f description="Multi-page dashboard with range charts. See docs/plans/02-time-series.md."
gh api repos/strumendo/fitme/milestones -f title="Phase 3 — Garmin metrics" \
  -f description="Activities, body battery, stress, HRV, sleep stages, body comp. See docs/plans/03-more-garmin.md."
gh api repos/strumendo/fitme/milestones -f title="Phase 4 — Manual inputs" \
  -f description="Training plan, training log, food log. See docs/plans/04-manual-inputs.md."
```

## 3. Create the Project (v2) board

User-level project owned by `@me`. The output URL ends in the project number,
which we capture for later `item-add` calls.

```bash
PROJECT_URL=$(gh project create --owner "@me" --title "fitme Roadmap" --format json | jq -r .url)
PROJECT_NUMBER=$(basename "$PROJECT_URL")
echo "Project #$PROJECT_NUMBER created at $PROJECT_URL"
```

> Add the custom fields (`Phase`, `Type`) and the `Board grouped by Status`
> view in the GitHub web UI after this step — the CLI in v2.45 doesn't yet
> support single-select field creation with predefined options.

## 4. Helper functions

Tiny shell helpers used by the issue-creation steps below. They keep the rest
of the script readable: `mk_issue` creates an issue and returns its number,
and `add_to_project` attaches it to the board.

```bash
mk_issue() {
  # mk_issue "<title>" "<body>" "<comma,labels>" "<milestone title>"
  gh issue create \
    --title  "$1" \
    --body   "$2" \
    --label  "$3" \
    --milestone "$4" \
    | tail -n 1 | awk -F/ '{print $NF}'
}

add_to_project() {
  # add_to_project <issue-number>
  gh project item-add "$PROJECT_NUMBER" --owner "@me" \
    --url "https://github.com/strumendo/fitme/issues/$1" >/dev/null
}
```

## 5. Create issues — Phase 1

Tasks first, epic last. The epic body references each task by number so
GitHub renders them as sub-issues with auto-tracking checkboxes.

```bash
P1_T1=$(mk_issue "Add src/fitme/db.py — connect, context manager, applies migrations" \
  "Implements the SQLite connection helper described in docs/plans/01-persistence.md (Approach → Module layout)." \
  "type:task,phase:1,area:db" "Phase 1 — Persistence")

P1_T2=$(mk_issue "Add src/fitme/db_schema.py — SCHEMA_VERSION + migrate()" \
  "Hand-written forward migrations applied on every connect. See docs/plans/01-persistence.md (Migration strategy)." \
  "type:task,phase:1,area:db" "Phase 1 — Persistence")

P1_T3=$(mk_issue "Add src/fitme/queries.py — read helpers per table" \
  "Single-date read helpers for daily_summary, heart_rate, sleep, weight. Range helpers come in Phase 2." \
  "type:task,phase:1,area:db" "Phase 1 — Persistence")

P1_T4=$(mk_issue "Add src/fitme/ingest.py — per-metric ingest functions and CLI" \
  "Idempotent INSERT OR REPLACE upserts, with --since / --from / --to / --date / --metrics flags. See docs/plans/01-persistence.md (Ingest)." \
  "type:task,phase:1,area:ingest" "Phase 1 — Persistence")

P1_T5=$(mk_issue "Wire FITME_DB_PATH into config.py and .env.example" \
  "Default to data/fitme.db. Surface the new env var in .env.example with a short comment." \
  "type:task,phase:1,area:db" "Phase 1 — Persistence")

P1_T6=$(mk_issue "Add data/ to .gitignore" \
  "Keep the SQLite file local. Verify no rows are committed." \
  "type:task,phase:1,area:db" "Phase 1 — Persistence")

P1_T7=$(mk_issue "Switch app.py to read from queries with empty-day fallback UI" \
  "Replace direct Garmin calls with queries.*. Show a banner + button to ingest a missing date on demand." \
  "type:task,phase:1,area:ui" "Phase 1 — Persistence")

P1_T8=$(mk_issue "Update root CLAUDE.md — new modules, commands, env var, data flow" \
  "Document db.py, db_schema.py, queries.py, ingest.py, FITME_DB_PATH, and that the dashboard reads from the DB." \
  "type:task,phase:1,area:docs" "Phase 1 — Persistence")

read -r -d '' P1_BODY <<EOF
## Goal

Own a local copy of the Garmin data so the dashboard and every later phase
can read history without hitting the Garmin Connect API on every view.

Plan: [docs/plans/01-persistence.md](../blob/main/docs/plans/01-persistence.md).

## Tasks

- [ ] #${P1_T1}
- [ ] #${P1_T2}
- [ ] #${P1_T3}
- [ ] #${P1_T4}
- [ ] #${P1_T5}
- [ ] #${P1_T6}
- [ ] #${P1_T7}
- [ ] #${P1_T8}

## Acceptance

- [ ] \`uv run python -m fitme.ingest --since 7d\` populates four tables.
- [ ] Re-running does not create duplicates.
- [ ] \`data/fitme.db\` is created on first run and never committed.
- [ ] Dashboard makes zero Garmin calls when the DB has the data.
- [ ] Empty days show a "fetch from Garmin" banner with a working button.
EOF

P1_EPIC=$(mk_issue "[Epic] Phase 1 — Local persistence (SQLite)" "$P1_BODY" \
  "type:epic,phase:1,area:db" "Phase 1 — Persistence")

for n in $P1_T1 $P1_T2 $P1_T3 $P1_T4 $P1_T5 $P1_T6 $P1_T7 $P1_T8 $P1_EPIC; do
  add_to_project "$n"
done
```

## 6. Create issues — Phase 2

```bash
P2_T1=$(mk_issue "Migrate app.py to 'Today' landing page" \
  "Keep current behavior; structure it as the landing of a multi-page app." \
  "type:task,phase:2,area:ui" "Phase 2 — Time series")

P2_T2=$(mk_issue "Add pages/2_Trends.py — range picker + 7/30/90d quick buttons" \
  "Streamlit native multi-page. See docs/plans/02-time-series.md." \
  "type:task,phase:2,area:ui" "Phase 2 — Time series")

P2_T3=$(mk_issue "Extend fitme/queries.py with *_range helpers (DataFrames)" \
  "One *_range per table (daily_summary, heart_rate, sleep, weight); each returns a DataFrame indexed by date." \
  "type:task,phase:2,area:db" "Phase 2 — Time series")

P2_T4=$(mk_issue "Add fitme/analysis.py — rolling() and period_delta()" \
  "Rolling 7-day overlay helper and period-over-period delta computation for st.metric." \
  "type:task,phase:2,area:ui" "Phase 2 — Time series")

P2_T5=$(mk_issue "Build per-metric chart sections on Trends page" \
  "Steps, HR, sleep, weight, calories, active minutes. Each: header, summary card, chart, rolling toggle." \
  "type:task,phase:2,area:ui" "Phase 2 — Time series")

P2_T6=$(mk_issue "Update root CLAUDE.md — multi-page layout, new modules, chart recipe" \
  "Document pages/ convention and 'where to add the next chart' note." \
  "type:task,phase:2,area:docs" "Phase 2 — Time series")

read -r -d '' P2_BODY <<EOF
## Goal

Move from "today only" to multi-day trends. Pick a date range and see how
steps, resting HR, sleep, and weight evolve over time.

Plan: [docs/plans/02-time-series.md](../blob/main/docs/plans/02-time-series.md).

## Tasks

- [ ] #${P2_T1}
- [ ] #${P2_T2}
- [ ] #${P2_T3}
- [ ] #${P2_T4}
- [ ] #${P2_T5}
- [ ] #${P2_T6}

## Acceptance

- [ ] Trends page renders four core charts with gaps (not zeros) for missing days.
- [ ] 7-day rolling-average toggle works per chart; on by default for weight + resting HR.
- [ ] 7/30/90d quick buttons re-render in <500 ms on local SQLite.
- [ ] Summary cards show period-over-period delta.
EOF

P2_EPIC=$(mk_issue "[Epic] Phase 2 — Time series + history view" "$P2_BODY" \
  "type:epic,phase:2,area:ui" "Phase 2 — Time series")

for n in $P2_T1 $P2_T2 $P2_T3 $P2_T4 $P2_T5 $P2_T6 $P2_EPIC; do
  add_to_project "$n"
done
```

## 7. Create issues — Phase 3

```bash
P3_T1=$(mk_issue "Activities — wrapper, table, ingest, queries, pages/3_Activities.py" \
  "Schema: activities(activity_id PK, date, start_time, type, duration_s, distance_m, calories_kcal, avg_hr_bpm, max_hr_bpm, raw_json, fetched_at)." \
  "type:task,phase:3,area:garmin" "Phase 3 — Garmin metrics")

P3_T2=$(mk_issue "Body battery — wrapper, table, ingest, queries, Trends chart" \
  "Daily series, same shape as daily_summary." \
  "type:task,phase:3,area:garmin" "Phase 3 — Garmin metrics")

P3_T3=$(mk_issue "Stress level — wrapper, table, ingest, queries, Trends chart" \
  "Daily and intra-day if available." \
  "type:task,phase:3,area:garmin" "Phase 3 — Garmin metrics")

P3_T4=$(mk_issue "HRV — wrapper, table, ingest, queries, Trends chart" \
  "Overnight values. Sensitive metric — flag missing data instead of zeroing." \
  "type:task,phase:3,area:garmin" "Phase 3 — Garmin metrics")

P3_T5=$(mk_issue "Sleep stages — extend sleep table, ingest stage breakdown, UI" \
  "Columns already in Phase 1 schema; this task wires the stage parsing + UI." \
  "type:task,phase:3,area:garmin" "Phase 3 — Garmin metrics")

P3_T6=$(mk_issue "Body composition — extend weight table, ingest, Today card" \
  "Body fat %, muscle mass, body water, bone mass from the Garmin scale." \
  "type:task,phase:3,area:garmin" "Phase 3 — Garmin metrics")

P3_T7=$(mk_issue "Update root CLAUDE.md — new tables, helpers, schema_version bump" \
  "Reflect all new tables and the final SCHEMA_VERSION after this phase." \
  "type:task,phase:3,area:docs" "Phase 3 — Garmin metrics")

read -r -d '' P3_BODY <<EOF
## Goal

Cover the rest of Garmin Connect data relevant to fitness evolution:
activities list, body battery, stress, HRV, sleep stages, body composition.

Plan: [docs/plans/03-more-garmin.md](../blob/main/docs/plans/03-more-garmin.md).

## Tasks

- [ ] #${P3_T1}
- [ ] #${P3_T2}
- [ ] #${P3_T3}
- [ ] #${P3_T4}
- [ ] #${P3_T5}
- [ ] #${P3_T6}
- [ ] #${P3_T7}

## Acceptance

- [ ] Activities page lists recent activities with type + date filters and a JSON-detail expander.
- [ ] Body battery, stress, and HRV appear on Trends with the Phase 2 UX (rolling avg toggle, period delta).
- [ ] Body composition shows on the Today page when data exists.
- [ ] \`uv run python -m fitme.ingest --since 30d --metrics all\` populates all new tables.
EOF

P3_EPIC=$(mk_issue "[Epic] Phase 3 — Expanded Garmin metrics" "$P3_BODY" \
  "type:epic,phase:3,area:garmin" "Phase 3 — Garmin metrics")

for n in $P3_T1 $P3_T2 $P3_T3 $P3_T4 $P3_T5 $P3_T6 $P3_T7 $P3_EPIC; do
  add_to_project "$n"
done
```

## 8. Create issues — Phase 4

```bash
P4_T1=$(mk_issue "Schema migration — training_plan, training_log, food_log tables" \
  "Bump SCHEMA_VERSION; add the three tables per docs/plans/04-manual-inputs.md (Schema)." \
  "type:task,phase:4,area:db" "Phase 4 — Manual inputs")

P4_T2=$(mk_issue "Add src/fitme/repository.py — CRUD for plan / log / food" \
  "Keep mutation logic out of pages. Plan, log, and food helpers live here." \
  "type:task,phase:4,area:db" "Phase 4 — Manual inputs")

P4_T3=$(mk_issue "Extend fitme/queries.py — plan_for_date, training_log_range, food_log_range, food_macros_summary" \
  "Read-side helpers used by the Training and Food pages." \
  "type:task,phase:4,area:db" "Phase 4 — Manual inputs")

P4_T4=$(mk_issue "Build pages/4_Training.py — plan editor, log form, plan-vs-actual view" \
  "Supersede plans by inserting new rows with a later effective_from. Link logs optionally to a Garmin activity_id." \
  "type:task,phase:4,area:ui" "Phase 4 — Manual inputs")

P4_T5=$(mk_issue "Build pages/5_Food.py — entry form, per-day totals, range macro trends" \
  "kcal + macros (protein/carbs/fat) per meal. No external nutrient DB in this phase." \
  "type:task,phase:4,area:ui" "Phase 4 — Manual inputs")

P4_T6=$(mk_issue "Extend app.py 'Today' — planned training + logged training + food totals" \
  "Show all three sections next to the Garmin block on the landing page." \
  "type:task,phase:4,area:ui" "Phase 4 — Manual inputs")

P4_T7=$(mk_issue "Edit/delete UIs for manual entries" \
  "Inline edit and confirm-delete on the Training and Food pages." \
  "type:task,phase:4,area:ui" "Phase 4 — Manual inputs")

P4_T8=$(mk_issue "Update root CLAUDE.md — new tables, pages, repository.py, plan-vs-actual UX" \
  "After this phase the docs should describe the full Garmin + routine + food vision." \
  "type:task,phase:4,area:docs" "Phase 4 — Manual inputs")

read -r -d '' P4_BODY <<EOF
## Goal

Capture the weekly training plan, log actual sessions, and record daily food
alongside Garmin-sourced data — closing the loop on the README's vision.

Plan: [docs/plans/04-manual-inputs.md](../blob/main/docs/plans/04-manual-inputs.md).

## Tasks

- [ ] #${P4_T1}
- [ ] #${P4_T2}
- [ ] #${P4_T3}
- [ ] #${P4_T4}
- [ ] #${P4_T5}
- [ ] #${P4_T6}
- [ ] #${P4_T7}
- [ ] #${P4_T8}

## Acceptance

- [ ] Weekly plan can be set up and superseded later without losing history.
- [ ] Sessions can be logged and optionally linked to a same-day Garmin activity.
- [ ] Food entries support kcal + macros; per-day totals and range view work.
- [ ] Today page surfaces Garmin + planned + actual training + food totals.
- [ ] Edit and delete work for all manual entries.
EOF

P4_EPIC=$(mk_issue "[Epic] Phase 4 — Manual inputs: training routine + food log" "$P4_BODY" \
  "type:epic,phase:4,area:ui" "Phase 4 — Manual inputs")

for n in $P4_T1 $P4_T2 $P4_T3 $P4_T4 $P4_T5 $P4_T6 $P4_T7 $P4_T8 $P4_EPIC; do
  add_to_project "$n"
done
```

## 9. Verify

Quick sanity checks after running everything.

```bash
gh issue list --label "type:epic" --state all
gh issue list --milestone "Phase 1 — Persistence" --state all
gh project item-list "$PROJECT_NUMBER" --owner "@me" --limit 100
echo "Project URL: $PROJECT_URL"
```

Open the project URL, add the custom `Phase` and `Type` fields, group the
Board view by `Status`, and you're ready to start working Phase 1.

## Rollback (if something goes wrong)

Deleting issues and the project board cleans up most of the noise.

```bash
# Delete the project (irreversible)
gh project delete "$PROJECT_NUMBER" --owner "@me"

# Close all issues created by this script (manual list — adjust if numbers differ)
gh issue list --label "type:epic" --state open --json number -q '.[].number' \
  | xargs -I {} gh issue close {}
gh issue list --label "type:task" --state open --json number -q '.[].number' \
  | xargs -I {} gh issue close {}
```

Milestones and labels can stay — they're cheap to keep and harmless if reused.
