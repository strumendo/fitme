# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project intent

Personal app to track fitness evolution by combining Garmin Connect data with the user's training routine and food log. Sole user/developer is the repo owner.

## Stack

- **Python 3.12** (pinned via `.python-version`)
- **uv** for env + dependency management (`pyproject.toml`, `uv.lock`)
- **Streamlit** as the UI layer — entry point is `app.py` at the repo root
- **garminconnect** (`cyberjunky/python-garminconnect`, installed from PyPI) as the Garmin data source. A reference clone lives outside the repo at `~/Documents/MyBrain/MyBrain/Resources/Garmin/python-garminconnect` — read it for API examples (`example.py`, `demo.py`) but do not vendor it.
- **python-dotenv** for credentials loaded from `.env` (gitignored; template in `.env.example`)
- **pandas** for data transforms feeding the dashboard

## Layout

```
app.py                  # Streamlit entry point
src/fitme/
  config.py             # loads .env into a Settings dataclass
  garmin.py             # get_client() + thin wrappers over the Garmin API
  login.py              # one-off interactive login (handles MFA)
  logging_config.py     # setup() called once per entry point
docs/plans/             # roadmap — one file per phase (see CLAUDE.md there)
pyproject.toml          # deps + hatchling build of src/fitme
.python-version         # 3.12
.env.example            # template — copy to .env locally
```

## Roadmap

Forward-looking work lives under [`docs/plans/`](docs/plans/README.md), one file
per phase. Current order: persistence (SQLite) → time-series view → expanded
Garmin metrics → manual inputs (training + food). When starting work on a
phase, read its plan file and update its `Status` header from `not started` →
`in progress`; mark it `done` only when the Acceptance checklist is met. Edit
plans in place — see [`docs/plans/CLAUDE.md`](docs/plans/CLAUDE.md) for the
maintenance rules specific to that folder.

## Commands

All commands assume `uv` is on PATH (installed to `~/.local/bin`).

| Task | Command |
| --- | --- |
| Install / sync deps | `uv sync` |
| Add a runtime dep | `uv add <pkg>` |
| Add a dev-only dep | `uv add --group dev <pkg>` |
| Run the dashboard | `uv run streamlit run app.py` |
| One-off Garmin login (handles MFA, caches tokens) | `uv run python -m fitme.login` |
| Ad-hoc Python in the env | `uv run python -c '...'` |
| Lint | `uv run ruff check .` |

## Garmin auth flow

1. First-time setup: user copies `.env.example` → `.env` and fills `GARMIN_EMAIL` / `GARMIN_PASSWORD`, then runs `uv run python -m fitme.login`. This handles MFA interactively and caches OAuth tokens at `$GARMINTOKENS` (default `~/.garminconnect/`).
2. Subsequent runs: `fitme.garmin.get_client()` restores cached tokens silently — no password or MFA needed until the refresh token expires.
3. **Streamlit cannot run the interactive MFA prompt**, so the dashboard relies on cached tokens. If `get_client()` raises `GarminAuthError`, the UI shows a message instructing the user to run `fitme.login` from the terminal.

Don't add Garmin password handling to `app.py` — keep auth concerns inside `fitme/garmin.py` and `fitme/login.py`.

## Documentation discipline — keep CLAUDE.md current

**Every code change ships with the matching CLAUDE.md update in the same turn.** Documentation is not a follow-up task; it lives next to the change.

When you (Claude) add a feature, a new module, a new entry point, a new command, a new dependency, a new env var, a new convention, or change an existing one — update the relevant `CLAUDE.md` *before declaring the task done*. Treat an out-of-date `CLAUDE.md` the same way you'd treat broken code.

What must be reflected in `CLAUDE.md`:
- **New applications or entry points** (CLIs, dashboards, scripts, services) — what they do, how to run them.
- **Stack changes** — added/removed dependencies, Python version bumps, package-manager switches.
- **New commands** in the "Commands" table — `uv add`, `uv run …`, lint, test, deploy, anything you'd want to remember.
- **New env vars** — also mirrored into `.env.example` with a short comment.
- **Architectural decisions** — auth flow, data flow, integration patterns, module layout.
- **Conventions** — coding rules, logging, error handling, naming.

**Sub-folder `CLAUDE.md` files** — if a sub-folder (e.g. `src/fitme/integrations/`, `infra/`, `docs/`) grows complex enough to need its own `CLAUDE.md`, create one and treat it with the same discipline: it documents that sub-tree, and changes to that sub-tree must update it in the same turn. The root `CLAUDE.md` stays the project-wide source of truth; sub-folder files cover details too specific to belong in the root. Link the sub-folder file from the root's "Layout" section so future Claude instances discover it.

When updating: edit in-place rather than appending notes at the bottom. Remove sections that no longer apply. Stale guidance is worse than missing guidance — it actively misleads.

## Git / VCS authorship

**Every commit, pull request, merge request, branch description and release note belongs to the user only: `Bruno Strumendo <strumendo@gmail.com>`.**

- Never add `Co-Authored-By: Claude ...` (or any other AI/tool co-author trailer) to commit messages.
- Never mention Claude, Claude Code, AI assistance, "generated with…", or similar in commit bodies, PR titles, PR descriptions, comments on issues/PRs, or any text that lands in git history or GitHub UI.
- Strip the default "🤖 Generated with [Claude Code]" footer from the `gh pr create` template.
- The local git config is already `user.name=Bruno Strumendo` / `user.email=strumendo@gmail.com`; do not change it.

This is a hard rule — it overrides any default that would otherwise add attribution.

## Conventions

- Package is `src/fitme` (src layout). When adding modules, place them under `src/fitme/` and import as `from fitme.x import y`.
- New API helpers (steps, sleep, activities, weight, body composition…) go in `src/fitme/garmin.py` as thin functions taking the `Garmin` client. Keep Streamlit code in `app.py` free of direct `garminconnect.Garmin` method calls — go through the wrapper so caching/error handling can be added in one place later.
- Never commit `.env` or anything under `~/.garminconnect/`.

### Logging — never use `print`

**Always use the `logging` module, never `print()`.** Diagnostic output, errors, status messages — everything goes through a logger. `print` calls should not appear in code under `src/fitme/` or in entry points.

- Each module declares its logger at the top:
  ```python
  import logging
  logger = logging.getLogger(__name__)
  ```
- Each entry point (`app.py`, `src/fitme/login.py`, future CLIs) calls `fitme.logging_config.setup()` **once** before any other code. It configures format + level (overridable via `LOG_LEVEL` in `.env`) and dampens `garminconnect`'s own logger to WARNING.
- Use lazy `%`-formatting (`logger.info("Got %s", x)`), not f-strings, so the message isn't built when the level is filtered out.
- For caught exceptions where the stacktrace matters, use `logger.exception(...)` (only inside an `except` block); for expected failures use `logger.warning` / `logger.error` with a short message.
- Streamlit UI calls (`st.error`, `st.warning`, `st.info`) are **UI output, not logs** — they're fine and are separate from the logging rule. Often you want both: log the technical detail, show the user a clean message.
- Avoid `console.log`-style debug prints during development too. If you need ad-hoc tracing, raise the level to DEBUG via `LOG_LEVEL=DEBUG` in `.env` and use `logger.debug(...)`.
