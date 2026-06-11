# Phase 9 — Nutrition coach: LLM daily targets + adherence

Status: in progress
Last updated: 2026-06-10

## Goal

Give the athlete daily nutrition targets (kcal + protein / carbs / fat)
tailored to their goal, then track adherence against those targets and
recalibrate over time. Targets are produced by **Claude** from a summary
of the goal, bodyweight trend, Garmin energy expenditure, recent intake,
and training load — the nutrition counterpart to phase 8's training coach.
The Food and Today pages then show "did I hit my targets today?", and when
bodyweight isn't moving toward the goal over weeks, the coach proposes a
calorie adjustment.

## Why now

- Phase 8 built the training coach and the LLM plumbing
  (`ANTHROPIC_API_KEY`, the `anthropic` dep, the
  build_context → generate → structured-output pattern). Nutrition reuses
  all of it.
- Phase 4 logs food (kcal + macros) and phase 6 made entry fast (Open Food
  Facts), but nothing tells the user *how much* to eat or whether they're
  on track. The data to recommend it — goal, bodyweight, Garmin
  expenditure, intake history — is all already in the DB.
- It closes the other half of the "what should I do" loop: training (phase
  8) + nutrition (phase 9).

## Decisions (locked)

- **Engine: Claude API (LLM).** Same pattern as the training coach — a
  structured summary in, a structured target out. Not a TDEE formula.
- **Scope: targets + adherence + adjustment.** Compute daily targets, show
  progress vs target on Food + Today, and recalibrate kcal when the
  bodyweight trend stalls against the goal.

## Inputs the model receives

A deterministic summary (no pandas, no network in the builder):

- **Goal** — preset + days/week (from `training_goal`, phase 8).
- **Bodyweight** — latest + multi-week trend (direction + rate), the key
  signal for the adjustment loop.
- **Energy expenditure** — average daily `daily_summary.calories_kcal`
  (Garmin-measured total burn) over a recent window. Avoids needing
  height/age/sex for a TDEE formula — use the measured number.
- **Recent intake** — average kcal + macros per *logged* day from
  `food_log`, plus how many days were logged (adherence signal).
- **Training load** — sessions/week + type mix (a hard week may warrant
  more carbs).

## Scope

**In:**
- **Schema v6** — `nutrition_target` table: `kcal`, `protein_g`,
  `carbs_g`, `fat_g`, `rationale`, `adjustment`, `created_at`. Append-only;
  latest row is the active target (same pattern as `training_goal`).
- **`src/fitme/nutrition.py`** — mirrors `coach.py`, split so the data half
  is testable offline:
  1. `build_context(conn, goal) -> dict` — the summary above from
     `queries.*` (no pandas, no network).
  2. `generate_targets(context) -> dict` — Claude call
     (`claude-opus-4-8`, adaptive thinking, `output_config.format`)
     returning `{kcal, protein_g, carbs_g, fat_g, rationale, adjustment}`.
     Only place that touches the network + `ANTHROPIC_API_KEY`. Failures →
     a clean `NutritionError` (mirrors `CoachError`).
- **Queries** — `active_nutrition_target`, average daily expenditure over a
  range (`daily_summary.calories_kcal`), recent intake averages (reuse /
  extend `food_macros_summary`), multi-week bodyweight trend (reuse
  `weight_range`), training frequency (reuse `training_type_mix`).
- **Targets UI** — a "Nutrition targets" section on the Food page
  (`pages/5_Food.py`): shows the active target + a "Generate / update
  targets" button that calls `generate_targets` and saves via
  `repository.insert_nutrition_target`. Renders the rationale + adjustment
  note. Graceful no-key path (like the Coach page).
- **Adherence** — Food day view shows the day's totals vs the active
  target (per-macro delta + kcal remaining); range trends overlay a target
  line on the kcal chart; the Today page shows kcal-vs-target for the day.
- **Adjustment loop** — the multi-week bodyweight trend + intake go into
  the context, and the output's `adjustment` field says hold / raise /
  lower kcal and why. Re-running the generation after a few weeks of data
  produces the recalibrated target.

**Out (deferred):**
- Per-meal planning or a meal generator — targets + adherence only.
- Micronutrients / fiber / hydration — macros + kcal in v1.
- Auto-regenerating targets on a schedule — user triggers it.
- A TDEE formula fallback — the LLM uses Garmin's measured expenditure.

## Approach

### Claude call (`nutrition.py`)

- Same shape as `coach.generate_program`: `anthropic.Anthropic(api_key=…)`,
  `claude-opus-4-8`, `thinking={"type": "adaptive"}`, `output_config.format`
  with a strict `TARGET_SCHEMA`
  (`{kcal:int, protein_g:int, carbs_g:int, fat_g:int, rationale:str,
  adjustment:str}`, `additionalProperties:false`, all required).
- Frozen system prompt: how to read expenditure vs intake vs bodyweight
  trend, how the goal preset maps to a deficit/surplus, protein guidance by
  bodyweight, and when to recommend an adjustment. Per-request summary in
  the user turn (cacheable prefix).
- Typed error handling → `NutritionError` with a clean message; log the
  technical detail via `logger.*`.

### UI (`pages/5_Food.py` + `app.py`)

- Thin orchestration (per `pages/CLAUDE.md`): `queries.*` to read,
  `nutrition.*` for the LLM, `st.*` to render. Active target held in the DB
  (not session state) so adherence reads it everywhere.
- Adherence rendering reuses the existing day-totals and `food_macros_summary`
  computations, adding target deltas and a target line.

### PR split (schema + LLM + UX → multiple PRs)

1. **PR 1 — foundations, no network.** Schema v6 (`nutrition_target`) +
   repository + queries (active target, expenditure avg, intake avg) +
   `nutrition.build_context`. Data only — no UI, since targets are
   LLM-only (nothing to render until PR 2). Fully testable without a key.
2. **PR 2 — LLM + targets UI + adherence.** `nutrition.generate_targets`,
   the Food "Nutrition targets" section (generate + save), adherence vs
   target on the Food day view / trends, and kcal-vs-target on Today. The
   adjustment note rides in the generation output.
3. **PR 3 (optional) — adjustment polish.** Sharpen the recalibration
   (multi-week stall detection in the prompt/context) and any Today polish.

## Tasks

1. Schema v6 `nutrition_target` (migration, idempotent) + repository
   insert + `queries.active_nutrition_target`.
2. Queries: average daily expenditure, recent intake averages, multi-week
   bodyweight trend (dict-based, pandas-free).
3. `nutrition.build_context(conn, goal)` assembling the summary.
4. `nutrition.generate_targets(context)` — Claude call, `TARGET_SCHEMA`,
   `NutritionError` handling.
5. Food page "Nutrition targets" section (generate + save + render
   rationale/adjustment); graceful no-key path.
6. Adherence: Food day view vs target, range-trend target line, Today
   kcal-vs-target.
7. Docs same-turn: `docs/plans/README.md` row 9, `pages/CLAUDE.md`,
   `src/fitme/CLAUDE.md` (nutrition module + schema v6 table), root
   `CLAUDE.md` stack note.
8. `ruff check .` clean; `streamlit run app.py` boots.

## Acceptance

- [ ] Migration v6 applies cleanly on an existing DB (idempotent).
- [ ] `nutrition.build_context` returns goal, bodyweight trend, avg
      expenditure, recent intake, and training load — verifiable without an
      API key.
- [ ] With a valid `ANTHROPIC_API_KEY`, generating targets returns a
      schema-valid `{kcal, protein_g, carbs_g, fat_g, rationale,
      adjustment}` and persists it.
- [ ] The Food day view and Today show the day's totals vs the active
      target (deltas + kcal remaining); range trends overlay the target.
- [ ] With no/invalid key, the targets section errors cleanly and the rest
      of the Food page is unaffected.
- [ ] A stalled bodyweight trend against the goal produces an `adjustment`
      that recommends changing kcal — spot-check.
- [ ] No regressions: `ruff check` clean; existing pages boot.

## Open questions

- **Where the coach lives.** Targets generation sits on the Food page to
  keep nutrition in one place (vs a separate Nutrition page). Revisit if
  the page gets crowded.
- **Expenditure window.** Average `calories_kcal` over ~14–30d; the exact
  window is tunable once real data shows how noisy Garmin's number is.
- **Protein source.** Bodyweight-based protein guidance lives in the system
  prompt; if it drifts, make it an explicit context field.
- **Adjustment cadence.** v1 recalibrates only when the user regenerates.
  A scheduled nudge ("weight stalled 2 weeks — update targets?") is a
  possible follow-up.

## Cross-phase notes

- Reuses phase 8 wiring verbatim: `ANTHROPIC_API_KEY`, the `anthropic` dep,
  and the build_context → generate → structured-output pattern. No new env
  var, no new dependency.
- Reads `training_goal` (phase 8) for the goal, `food_log` (phase 4) for
  intake, `daily_summary` (phase 1) for expenditure, `weight` (phase 1) for
  the trend. No schema changes to those tables.
- The export/backup pipeline picks up `nutrition_target` automatically via
  its `sqlite_master` discovery.
