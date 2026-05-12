# Phase 2 — Time series + history view

Status: done
Last updated: 2026-05-12

## Goal

Move from "today only" to multi-day trends. The user should be able to pick a
date range and see how steps, resting HR, sleep, and weight evolve over time.

## Why now

- Local DB from Phase 1 is in place — range queries are cheap and don't touch
  the Garmin API.
- Establishes the multi-page Streamlit pattern so Phases 3–4 plug into it.

## Scope

**In:**
- Streamlit multi-page app: keep `app.py` ("Today") and add `pages/2_Trends.py`.
- Date range picker (default: last 30 days; quick buttons for 7d / 30d / 90d).
- One line chart per metric (steps, resting HR, sleep duration, weight),
  plus calories and active minutes.
- 7-day rolling average overlay (toggleable per chart).
- Week-over-week and month-over-month summary cards on top of the Trends page.

**Out:**
- Predictive analytics, anomaly detection, ML.
- Per-activity drill-down (Phase 3).
- Custom dashboard layouts / saved views.

## Approach

### Page structure

Streamlit native multi-page (numbered files in `pages/`):

```
app.py                  # "Today" — already exists, becomes the landing page
pages/
  2_Trends.py           # range-based charts
  # (3_Activities.py, 4_Training.py etc. arrive in later phases)
```

### Data flow

`fitme.queries` (added in Phase 1) grows two range-returning helpers per table:

```python
def daily_summary_range(conn, start: date, end: date) -> pd.DataFrame: ...
def heart_rate_range(conn, start: date, end: date) -> pd.DataFrame: ...
def sleep_range(conn, start: date, end: date) -> pd.DataFrame: ...
def weight_range(conn, start: date, end: date) -> pd.DataFrame: ...
```

Each returns a DataFrame indexed by date. The Trends page calls these and
hands the result to `st.line_chart`. Missing days appear as gaps (don't fill
with zeros — that's misleading).

### Rolling averages

A small `fitme.analysis.rolling(df, window=7)` helper that returns a DataFrame
with `_avg` columns added. The page renders the raw line + the average overlay
when the toggle is on.

### Summary cards

For each metric: this-period mean vs. previous-period mean, with delta and
arrow. Compute in Python, render via `st.metric(label, value, delta)`.

## Tasks

1. Migrate `app.py` to be the "Today" landing page; ensure it still works.
2. Add `pages/2_Trends.py` with the range picker and quick-range buttons.
3. Extend `fitme/queries.py` with `*_range` helpers (DataFrames).
4. Add `fitme/analysis.py` with `rolling()` and a `period_delta()` helper.
5. Build per-metric chart sections in the Trends page (steps, HR, sleep,
   weight, calories, active minutes). Each: header, summary card, chart,
   rolling-average toggle.
6. Update root `CLAUDE.md`: document the multi-page layout, new modules,
   "where to add the next chart" note for Phase 3.
7. Update this file's status to `done` once Acceptance is met.

## Acceptance

- [ ] Trends page renders the four core charts for the chosen range without
      errors when some days are missing in the DB (gaps, not zeros).
- [ ] 7-day rolling-average toggle works per-chart and is on by default for
      weight + resting HR (noisy series).
- [ ] Quick-range buttons (7d / 30d / 90d) update the range picker and
      re-render in <500 ms on a typical local SQLite.
- [ ] Summary cards show period-over-period delta (this 30d vs prior 30d).

## Open questions

- Should Trends share state with the "Today" page (e.g., selected metric
  filters)? Default: independent pages, no shared state — keeps it simple.
- Charts: stick with `st.line_chart` or move to `plotly` / `altair` for
  multi-line and hover details? Default: native first; revisit if hover and
  multiple series become limiting.

## Cross-phase notes

- The `pages/` convention is what Phases 3 and 4 will extend.
- Don't bake `pandas` types into `queries.py` if it can be avoided — keep the
  table → dict conversion there and let `analysis.py` / pages wrap DataFrames.
  This makes the DB layer easier to test without pandas in the loop.
