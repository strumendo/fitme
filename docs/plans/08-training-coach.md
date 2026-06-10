# Phase 8 — Training coach: LLM-generated weekly program

Status: done
Last updated: 2026-06-10

## Goal

Generate a recommended **weekly training program** tailored to a chosen
goal, using the data already in the DB: training history (frequency,
volume, exercise progression), time since the last session (layoff),
bodyweight + trend, and Garmin recovery signals (sleep, body battery, HRV,
stress). The program is produced by **Claude (Anthropic API)** from a
structured summary of that data, so it can reason about trade-offs
(deconditioning after a layoff, low recovery week, bodyweight trend vs
goal) instead of applying a fixed rule table.

## Why now

- Phases 1–7 turned the app into a complete *recording* surface (Garmin
  metrics, training plan + log + sets, food). The data is there; nothing
  yet *acts on it* to tell the user what to actually do.
- The strength data (phase 7) and recovery metrics (phase 3) are the two
  inputs that make a recommendation non-trivial — both now exist.
- It's the first feature that closes the loop from "here's what happened"
  to "here's what to do next".

## Decisions (locked)

These were chosen up front; the plan is built around them.

- **Engine: Claude API (LLM).** A structured data summary is sent to
  Claude, which returns a structured weekly program. Not a Python rule
  engine. Rationale: flexible reasoning over many noisy inputs, explains
  itself, easy to evolve by prompt.
- **Output: full weekly program.** A 7-day split (per weekday: focus,
  description, target duration, and — for strength days — key exercises
  with suggested set×rep×load progression), plus a short rationale. Not
  just "today's session".
- **Goal: structured presets.** The user picks one of a fixed set
  (hypertrophy / strength / fat loss / maintenance / endurance) plus a
  couple of structured knobs (days/week available, session length). No
  free-text goal in v1.

## Inputs the model receives

Built server-side into a compact, deterministic summary (so it's
prompt-cacheable and auditable):

- **Goal** — preset + days/week + target session length.
- **Training history** — last ~90d: sessions/week, activity-type mix,
  per-exercise progression (latest working weight×reps and trend) from
  `exercise_set` + `training_log`.
- **Layoff** — days since the most recent `training_log` entry; flag long
  gaps explicitly (the model should ramp volume back, not resume at peak).
- **Bodyweight** — latest `weight` + 30/90d trend direction.
- **Recovery (Garmin)** — recent averages for sleep duration, body
  battery, HRV, resting stress (last ~7–14d), so the model can dial total
  volume for a low-recovery week.

## Scope

**In:**
- **Schema v5** — `training_goal` table: the active goal preset +
  days/week + session-length target + `created_at`. One row = one goal
  version; latest row is the active goal (history kept, like
  `training_plan`'s `effective_from` pattern).
- **Config / env** — `ANTHROPIC_API_KEY` env var (read in
  `src/fitme/config.py`, documented in `.env.example` and the CLAUDE.md
  env-var tables). The `anthropic` SDK added via `uv add anthropic`.
- **`src/fitme/coach.py`** — two responsibilities, split so the data half
  is testable without the network:
  1. `build_context(conn, goal) -> dict` — assemble the deterministic
     summary above from `queries.*` (no pandas, no network).
  2. `generate_program(context) -> dict` — call Claude
     (`model="claude-opus-4-8"`, `thinking={"type": "adaptive"}`,
     `output_config.format` with a JSON schema for the weekly program) and
     return the validated program. Network + key live only here.
- **Queries** — read-only helpers feeding `build_context`:
  `days_since_last_session`, training frequency/mix over a range, recovery
  averages over a range. Reuse existing `exercise_history` /
  `exercise_names` for per-exercise progression; reuse weight queries for
  bodyweight trend.
- **Goals UI** — a small "Goal" section (preset select + days/week +
  session length) that writes a `training_goal` row via `repository.*`.
  Lives on the Training page (`pages/4_Training.py`) next to the planner.
- **Coach page** (`pages/6_Coach.py`) — shows the active goal + a data
  snapshot (frequency, layoff, bodyweight trend, recovery), a "Generate
  program" button → renders the weekly program (table per day + the
  model's rationale). Handles a missing/invalid `ANTHROPIC_API_KEY`
  gracefully (clear `st.error`, no traceback).
- **Save as plan** (PR 3) — a button writes the generated week into
  `training_plan` as a new version (`effective_from = today`), mapping
  `focus`→`activity_type` and flattening description + exercises into the
  slot's `description`. The Today page (`app.py`) already reads the day's
  slot via `plan_for_date`, so the recommended session surfaces there with
  no `app.py` change.

**Out (deferred):**
- Free-text goals (needs the LLM path but adds prompt-injection / scope
  surface — revisit once presets are in use).
- Food/macro recommendations — this phase is training only.
- Caching/persisting generated programs — regenerate on demand; a single
  call is cheap and the inputs drift daily.

## Approach

### Claude API call (`coach.py`)

- Client: `anthropic.Anthropic()` — resolves `ANTHROPIC_API_KEY` from the
  environment (loaded via the existing dotenv path in `config.py`); do not
  hardcode a key.
- `model="claude-opus-4-8"`, `thinking={"type": "adaptive"}`,
  `max_tokens` generous (weekly program + rationale fits well under 16K, so
  non-streaming is fine).
- **Structured output**: pass `output_config={"format": {"type":
  "json_schema", "schema": PROGRAM_SCHEMA}}` so the response is a
  guaranteed-shape JSON weekly program — no brittle parsing. Schema:
  `{ rationale: str, week: [ { weekday: 0-6, focus: str, description: str,
  target_duration_min: int|null, exercises: [ { name, sets, reps,
  suggested_load: str } ] } ] }` (exact fields finalized in the PR).
- System prompt frozen (coaching instructions, how to read the inputs,
  how to handle a layoff / low-recovery week); the per-request data summary
  goes in the user turn. Keeps the system prompt cacheable.
- Errors: catch `anthropic.AuthenticationError` (missing/bad key) and
  `anthropic.APIError`; log the technical detail (`logger.*`, never
  `print`) and surface a clean `st.error` on the page.

### Page (`pages/6_Coach.py`)

- Standard page header. Read active goal + context via
  `with connect() as conn:`; render the snapshot. "Generate" button calls
  `coach.generate_program` and renders the result. Thin orchestration per
  `pages/CLAUDE.md`: `queries.*` to read, `coach.*` for the LLM, `st.*` to
  render — no inline SQL, no direct SDK calls in the page beyond
  `coach.generate_program`.

### PR split (per the multi-PR convention for schema+UX phases)

1. **PR 1 — foundations, no network.** ✅ Schema v5 (`training_goal`) +
   repository helpers + goals UI on the Training page +
   `ANTHROPIC_API_KEY` in config/`.env.example`/docs + `coach.build_context`
   and its supporting queries. Fully testable without an API key.
2. **PR 2 — LLM + Coach page.** ✅ `uv add anthropic`,
   `coach.generate_program` (Claude call + structured output), the Coach
   page rendering the program, error handling for a missing key.
3. **PR 3 — "save as plan".** ✅ Turn a generated week into `training_plan`
   rows (new version, `effective_from = today`); the Today page surfaces
   the day's recommended session for free via `plan_for_date`.

## Tasks

1. Schema v5 `training_goal` (migration, idempotent) + repository
   insert/read + `queries` for the active goal.
2. Goals UI section on `pages/4_Training.py` (preset + days/week + session
   length), writing via `repository.*`.
3. `ANTHROPIC_API_KEY` wired into `config.py`, `.env.example`, root +
   `src/fitme` CLAUDE.md env-var tables.
4. `queries`: `days_since_last_session`, training frequency/mix, recovery
   averages (all dict-based, pandas-free).
5. `coach.build_context(conn, goal)` assembling the summary.
6. `uv add anthropic`; `coach.generate_program(context)` — Claude call,
   adaptive thinking, `output_config.format` schema, typed error handling.
7. `pages/6_Coach.py` — snapshot + generate + render + graceful no-key
   path.
8. Docs: `docs/plans/README.md` row 8, `pages/CLAUDE.md` (new Coach page +
   pattern), `src/fitme/CLAUDE.md` (coach module, new env var, `anthropic`
   dep), root `CLAUDE.md` stack/env tables. Update in the same turn as code.
9. `ruff check .` clean; `streamlit run app.py` boots.

## Acceptance

- [x] Migration v5 applies cleanly on an existing DB (idempotent).
- [x] Setting a goal on the Training page persists a `training_goal` row;
      the latest row is treated as active.
- [x] `coach.build_context` returns a summary with goal, history, layoff,
      bodyweight trend, and recovery averages — verifiable without an API
      key.
- [x] With a valid `ANTHROPIC_API_KEY`, the Coach page generates a 7-day
      program (schema-valid JSON) plus a rationale and renders it.
      *(verified headless against the live API: 7-day schema-valid program
      + rationale.)*
- [x] With no/invalid key, the page shows a clean error (no traceback) and
      the rest of the app is unaffected.
- [x] A long layoff in the data visibly changes the recommendation (model
      ramps volume rather than resuming at peak) — spot-check.
      *(verified: identical data except layoff → regular run continued Bench
      at 72.5 kg, 24-day layoff deloaded to 62.5 kg "to re-ramp".)*
- [x] No regressions: `ruff check` clean; existing pages boot.

## Open questions

- **"Save as plan".** Resolved (PR 3): a button appends the generated week
  as a new `training_plan` version (`effective_from = today`), so the
  planner and Today page pick it up. Older versions are kept.
- **Free-text goal.** Presets only for now. If the presets feel too coarse
  once in use, add an optional free-text "notes to the coach" field that
  rides along in the user turn (the LLM path already supports it) — guard
  against prompt-injection since it flows into the model.
- **Cost / model.** `claude-opus-4-8` for quality; one call per generate is
  cheap. If generation feels slow or pricey in practice, `claude-sonnet-4-6`
  is the fallback — but that's the user's call, not a default downgrade.
- **Exercise selection.** v1 lets the model pick exercises (optionally
  biased toward names already in `exercise_set` history). A future version
  could constrain to a known exercise library once one exists (ties into
  the phase-7 "canonical exercise names" open question).

## Cross-phase notes

- No change to the export/backup pipeline beyond the new `training_goal`
  table, which its `sqlite_master` discovery picks up automatically.
- `ANTHROPIC_API_KEY` is the first external-API credential besides Garmin;
  same rules apply — never commit `.env`, document in `.env.example` only.
- Builds directly on phase 7 (`exercise_set` for progression) and phase 3
  (recovery metrics); no schema changes to those tables.
