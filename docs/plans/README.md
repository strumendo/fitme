# Roadmap

Plans for upcoming work, ordered. Each file is a self-contained scope + approach
for one phase. Status is tracked in the header of each file.

| # | Phase | Status | File |
| --- | --- | --- | --- |
| 1 | Local persistence (SQLite) | done | [01-persistence.md](01-persistence.md) |
| 2 | Time series + history view | done | [02-time-series.md](02-time-series.md) |
| 3 | Expanded Garmin metrics | done | [03-more-garmin.md](03-more-garmin.md) |
| 4 | Manual inputs — training + food | done | [04-manual-inputs.md](04-manual-inputs.md) |
| 5 | Export & backup of fitme.db | done | [05-export-backup.md](05-export-backup.md) |
| 6 | Open Food Facts lookup | done | [06-open-food-facts.md](06-open-food-facts.md) |

## Why this order

1. **Persistence first** — Phases 2–4 all want historical data, and the Garmin
   Connect API is rate-limited and doesn't always reach far back. Owning a local
   copy unblocks everything else and is cheap to build.
2. **Time series second** — Once history is in SQLite, charts are essentially a
   query + `st.line_chart`. Doing this before expanding metrics means the
   "add a metric" recipe (schema → ingest → chart) is already established when
   Phase 3 starts.
3. **More Garmin metrics third** — With the persistence + visualization wiring in
   place, adding sleep stages / activities / body battery / etc. becomes
   mechanical.
4. **Manual inputs last** — Training routine and food log involve forms,
   validation, edit/delete UIs, and FK-style relationships with the Garmin
   tables. Easier to build on top of a mature dashboard skeleton.

## How to use these plans

- Pick a phase, read its plan, execute the tasks, update the status header as
  you progress (`not started` → `in progress` → `done`), update `Last updated`.
- Cross-phase changes (e.g. a new env var that benefits two phases) should be
  applied at the phase that needs it first; just note it in the later phase's
  doc so we don't redo it.
- If reality diverges from the plan, **edit the plan in place** before or
  alongside the code change. A stale plan is worse than no plan.
- See [CLAUDE.md](CLAUDE.md) in this folder for the maintenance rules.
