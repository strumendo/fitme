# CLAUDE.md — docs/plans

Rules for working with files under `docs/plans/`. The root `CLAUDE.md` is still
the project-wide source of truth; this file only covers what's specific to this
sub-tree.

## What lives here

Forward-looking plans, one file per phase, executed roughly in numeric order.
This is the project's roadmap. It is **not** a changelog, **not** a decisions
record, and **not** a task tracker for in-flight work (use TaskCreate for that).

Once a phase is implemented, its plan file stays — it becomes a "this is what
we built and why" record. Mark its status `done` and update `Last updated`.

## File format

Every plan file starts with this header:

```
# Phase N — Title

Status: not started | in progress | done
Last updated: YYYY-MM-DD
```

Then the body uses these sections, in this order, omitting any that don't apply:
**Goal**, **Why now**, **Scope (in / out)**, **Approach**, **Tasks**,
**Acceptance**, **Open questions**, **Cross-phase notes**.

## Maintenance rules

- **Update the plan in the same turn as the code change**, not after. Same rule
  as the root `CLAUDE.md` discipline section.
- **Edit in place.** Don't append "update: …" blocks at the bottom; revise the
  affected section. The plan should always read as the current intent, not a
  log of edits — git history covers the log.
- **If scope shifts, update the plan before writing code.** If you discover the
  approach in the doc is wrong while implementing, stop, fix the doc, then
  resume. Future-Claude will read the doc and trust it.
- **Status transitions:**
  - `not started` → `in progress` when work begins.
  - `in progress` → `done` only when the **Acceptance** checklist is fully met.
    Partial work stays `in progress`.
- **Cross-references:** when a plan references project code (modules, env vars),
  use the same name as in the code so grep finds both.
- **New phases:** add the file, add a row to [README.md](README.md), keep
  numbering contiguous.
