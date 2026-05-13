"""Thin client over the Open Food Facts public REST API.

Used by the Food page to prefill kcal + macro fields when adding an entry.
Manual entry stays available — every public helper here returns ``[]`` or
``None`` on any failure so the page never has to handle exceptions.

API docs: https://wiki.openfoodfacts.org/API
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

BASE_URL = "https://world.openfoodfacts.org"
USER_AGENT = "fitme/0.1 (personal-dashboard; https://github.com/strumendo/fitme)"
TIMEOUT_SECONDS = 5.0


def _fetch_json(url: str) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as err:
        logger.warning("OFF request failed: %s", err)
    except (TimeoutError, json.JSONDecodeError):
        logger.exception("OFF request failed")
    return None


def _as_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize(product: dict) -> dict | None:
    """Convert a raw OFF product dict into the shape the page expects.

    Returns ``None`` when essential fields (code, name) are missing or the
    product carries no usable kcal value — those rows aren't worth showing.
    """
    code = product.get("code") or product.get("_id")
    name = product.get("product_name") or product.get("generic_name")
    if not code or not name:
        return None
    nutriments = product.get("nutriments") or {}
    kcal = (
        _as_float(nutriments.get("energy-kcal_100g"))
        or _as_float(nutriments.get("energy-kcal"))
    )
    if kcal is None:
        return None
    return {
        "code": str(code),
        "name": str(name).strip(),
        "brand": (product.get("brands") or None),
        "kcal_per_100g": kcal,
        "protein_per_100g": _as_float(nutriments.get("proteins_100g")),
        "carbs_per_100g": _as_float(nutriments.get("carbohydrates_100g")),
        "fat_per_100g": _as_float(nutriments.get("fat_100g")),
        "image_url": product.get("image_small_url") or product.get("image_url"),
    }


def search(query: str, *, lang: str = "pt", page_size: int = 10) -> list[dict]:
    """Search the OFF catalog. Returns up to ``page_size`` normalized hits."""
    query = (query or "").strip()
    if not query:
        return []
    params = urllib.parse.urlencode(
        {
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": page_size,
            "lc": lang,
        }
    )
    url = f"{BASE_URL}/cgi/search.pl?{params}"
    payload = _fetch_json(url)
    if not payload:
        return []
    products = payload.get("products") or []
    out: list[dict] = []
    for raw in products:
        normalized = _normalize(raw)
        if normalized:
            out.append(normalized)
    logger.info("OFF search %r → %d usable hits", query, len(out))
    return out


def lookup_barcode(code: str) -> dict | None:
    """Fetch a single product by EAN/UPC code. Returns ``None`` if not found."""
    code = (code or "").strip()
    if not code:
        return None
    url = f"{BASE_URL}/api/v2/product/{urllib.parse.quote(code)}.json"
    payload = _fetch_json(url)
    if not payload:
        return None
    if payload.get("status") != 1:
        logger.info("OFF barcode %s not found", code)
        return None
    product = payload.get("product") or {}
    return _normalize(product)
