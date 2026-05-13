# Phase 6 — Open Food Facts lookup

Status: done
Last updated: 2026-05-13

## Goal

Stop typing kcal and macro grams by hand for every food entry. Add a
search box on the Food page that hits the Open Food Facts public API,
returns a short list of matching products, and prefills the existing form
fields when one is picked. Manual entry stays available for items that
the DB doesn't know about (home cooking, restaurant meals, etc.).

## Why now

- Phase 4 shipped `food_log` with `kcal` / `protein_g` / `carbs_g` /
  `fat_g` columns already in place. Schema doesn't need to change.
- Open Food Facts is free, no auth, has decent BR coverage for packaged
  items, and exposes both text search and barcode lookup over plain JSON.
- Phase 5 (export/backup) means we can rebuild the DB easily if a bad
  experiment with the new field shows up later. Lower risk.

## Scope

**In:**
- New module `src/fitme/openfoodfacts.py` — thin client over the Open Food
  Facts REST API. Two public entry points:
  - `search(query, *, lang="pt", page_size=10) -> list[dict]`
  - `lookup_barcode(code) -> dict | None`
- Search section on top of `pages/5_Food.py`:
  - Text input + "Search" button (form so Enter submits).
  - Optional barcode input (just paste the code; no camera).
  - Result list (name + brand + per-100g kcal/macros + image thumbnail
    if available). Each result has a "Use this" button.
  - Clicking "Use this" stores the selection in `st.session_state` and
    the existing Add-entry form below renders with the kcal / macro
    fields prefilled. User adjusts portion size (g) — that scales the
    macros at save time — and submits as usual.
- Caching via `@st.cache_data(ttl=86400)` on the search + barcode
  helpers — same query inside a 24h window doesn't re-hit the network.
- Graceful failure: if the API is unreachable or returns nothing useful,
  log + `st.warning(...)`, keep the manual form fully functional.

**Out:**
- Barcode **scanning** (camera input). The paste-the-number flow covers
  the common case; camera support would add an upstream JS dep.
- DB cache of search results. In-process `@st.cache_data` is enough for
  now; if we restart Streamlit often and the cost is felt, layer a small
  table on top later.
- Editing existing entries with a re-lookup. Edits stay manual.
- Bulk import / nutrition history backfill from receipts.
- Localization of the result UI (labels stay PT-BR informal regardless of
  the result language).

## Approach

### Module: `src/fitme/openfoodfacts.py`

- Use stdlib `urllib.request` + `json` to keep dependencies flat — single
  call surface, no need for `requests`/`httpx`.
- Base URL: `https://world.openfoodfacts.org`.
- Search endpoint: `/cgi/search.pl?search_terms=<q>&search_simple=1&action=process&json=1&page_size=<n>&lc=<lang>`.
- Barcode endpoint: `/api/v2/product/<code>.json`.
- Normalize the API response into a `dict`:
  ```python
  {
      "code": str,
      "name": str,
      "brand": str | None,
      "kcal_per_100g": float | None,
      "protein_per_100g": float | None,
      "carbs_per_100g": float | None,
      "fat_per_100g": float | None,
      "image_url": str | None,
  }
  ```
- Set a tight timeout (5 s) and a project User-Agent header (Open Food
  Facts asks API clients to identify themselves).
- All network errors are caught and logged via `logger.exception(...)`;
  the public helpers return `[]` / `None` on failure rather than raising.

### UI changes in `pages/5_Food.py`

- New section at the top of the page: "Find a product". Two inputs side
  by side — text search and barcode — each in its own mini form so they
  submit independently. Results land below.
- Hits render as a list. Each row: thumbnail (small), name + brand,
  per-100g kcal + macro summary, "Use this" button keyed by product code.
- Clicking "Use this" sets `st.session_state["food_prefill"]` with the
  product + a default portion of 100 g. The existing Add-entry form
  picks that up and prefills `description` (name + brand), the macro
  fields scaled by portion, and adds a portion input (`grams`).
- "Clear selection" button next to the form to drop the prefill.
- Saving the entry behaves exactly like before — `repository.insert_food_log`
  with the scaled macros and the description.

### Caching strategy

```python
@st.cache_data(ttl=86_400)
def cached_search(query: str, lang: str) -> list[dict]: ...

@st.cache_data(ttl=86_400)
def cached_barcode(code: str) -> dict | None: ...
```

Cache keys on the literal arguments — `st.cache_data` handles that. TTL
24 h keeps the cache from going stale if product info changes upstream.

## Tasks

1. Add `src/fitme/openfoodfacts.py` with `search`, `lookup_barcode`, and
   shared normalization helper.
2. Extend `pages/5_Food.py`:
   - "Find a product" section + cached helpers.
   - Wire session state for the prefill flow.
   - Add portion (g) input in the Add-entry form when a prefill exists.
3. Update `src/fitme/CLAUDE.md` — list the new module, note it lives
   alongside `garmin.py` as another external-API wrapper.
4. Update `pages/CLAUDE.md` — short note about the prefill flow on the
   Food page (where it sits, that it falls back to manual entry).
5. Manual smoke: search a real product, paste a real barcode, hit "Use
   this", confirm save round-trips through `repository.insert_food_log`
   with the scaled macros.
6. Status → `done`, acceptance ticked.

## Acceptance

- [x] Searching a product name returns up to 10 matches with the four
      macro fields populated where the source had them.
- [x] Pasting a barcode returns either one product or a clear "not
      found" message.
- [x] "Use this" prefills the Add-entry form; changing the portion (g)
      rescales kcal/protein/carbs/fat at save time.
- [x] Saved entry shows up correctly in the Day view with the rescaled
      totals.
- [x] API failure (offline, timeout) shows a friendly warning and leaves
      the manual form usable. No exceptions reach the page.
- [x] `ruff check` clean; `streamlit run app.py` boots cleanly.

## Open questions

- **Language fallback** — search with `lc=pt`, fall back to global if
  results look thin? Default for now: `lc=pt` only; expand later if BR
  coverage frustrates.
- **Portion default** — 100 g (matches the API's per-100g basis) is the
  obvious default. If a product carries a `serving_size` field, could
  use that as the default instead. Probably overkill for now.
- **Persistent cache** — if `@st.cache_data` proves insufficient (slow
  restarts, repeated same-day lookups across sessions), revisit with a
  small `off_cache(code, payload, fetched_at)` table.

## Cross-phase notes

- The Food day view + range trends already use the totals stored in
  `food_log`. No changes there — they pick up scaled values
  automatically.
- A future phase could add a "favorites" feature (frequently used
  products pinned at the top of the search) without schema changes —
  just a new local table.
