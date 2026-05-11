"""Pull Garmin Connect data into the local fitme SQLite DB.

Idempotent: every metric is upserted via ``INSERT OR REPLACE`` keyed by date,
so re-running the same window does not create duplicates. The full Garmin
payload is stored in ``raw_json`` for forward compatibility — later schema
versions can backfill new typed columns from existing rows.

CLI::

    uv run python -m fitme.ingest --since 30d
    uv run python -m fitme.ingest --from 2026-04-01 --to 2026-04-30
    uv run python -m fitme.ingest --date 2026-05-10
    uv run python -m fitme.ingest --since 7d --metrics summary,sleep
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from garminconnect import Garmin

from fitme import garmin as gconn
from fitme.db import connect
from fitme.garmin import GarminAuthError, get_client
from fitme.logging_config import setup as setup_logging

logger = logging.getLogger(__name__)

METRICS: tuple[str, ...] = ("summary", "heart_rate", "sleep", "weight")


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _seconds_to_minutes(value: object) -> int | None:
    if isinstance(value, (int, float)):
        return int(value) // 60
    return None


def _grams_to_kg(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value) / 1000.0
    return None


def ingest_daily_summary(client: Garmin, conn: sqlite3.Connection, day: date) -> bool:
    try:
        payload = gconn.daily_summary(client, day)
    except Exception:
        logger.exception("daily_summary fetch failed for %s", day)
        return False
    if not payload:
        logger.info("no daily_summary data for %s", day)
        return False
    conn.execute(
        """
        INSERT OR REPLACE INTO daily_summary
            (date, steps, distance_m, calories_kcal, active_minutes,
             floors_climbed, raw_json, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            day.isoformat(),
            payload.get("totalSteps"),
            payload.get("totalDistanceMeters"),
            payload.get("totalKilocalories"),
            _seconds_to_minutes(payload.get("activeSeconds")),
            payload.get("floorsAscended"),
            json.dumps(payload),
            _now_iso(),
        ),
    )
    return True


def ingest_heart_rate(client: Garmin, conn: sqlite3.Connection, day: date) -> bool:
    try:
        payload = gconn.heart_rate(client, day)
    except Exception:
        logger.exception("heart_rate fetch failed for %s", day)
        return False
    if not payload:
        logger.info("no heart_rate data for %s", day)
        return False
    conn.execute(
        """
        INSERT OR REPLACE INTO heart_rate
            (date, resting_bpm, max_bpm, min_bpm, avg_bpm, raw_json, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            day.isoformat(),
            payload.get("restingHeartRate"),
            payload.get("maxHeartRate"),
            payload.get("minHeartRate"),
            payload.get("avgHeartRate")
            or payload.get("lastSevenDaysAvgRestingHeartRate"),
            json.dumps(payload),
            _now_iso(),
        ),
    )
    return True


def ingest_sleep(client: Garmin, conn: sqlite3.Connection, day: date) -> bool:
    try:
        payload = gconn.sleep(client, day)
    except Exception:
        logger.exception("sleep fetch failed for %s", day)
        return False
    if not payload:
        logger.info("no sleep data for %s", day)
        return False
    dto = (payload.get("dailySleepDTO") or {}) if isinstance(payload, dict) else {}
    conn.execute(
        """
        INSERT OR REPLACE INTO sleep
            (date, total_seconds, deep_seconds, light_seconds, rem_seconds,
             awake_seconds, raw_json, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            day.isoformat(),
            dto.get("sleepTimeSeconds"),
            dto.get("deepSleepSeconds"),
            dto.get("lightSleepSeconds"),
            dto.get("remSleepSeconds"),
            dto.get("awakeSleepSeconds"),
            json.dumps(payload),
            _now_iso(),
        ),
    )
    return True


def ingest_weight(client: Garmin, conn: sqlite3.Connection, day: date) -> bool:
    try:
        payload = gconn.body_composition(client, day)
    except Exception:
        logger.exception("weight fetch failed for %s", day)
        return False
    target = (payload or {}).get("totalAverage") if isinstance(payload, dict) else None
    if not target or target.get("weight") in (None, 0):
        logger.info("no weight data for %s", day)
        return False
    conn.execute(
        """
        INSERT OR REPLACE INTO weight
            (date, weight_kg, body_fat_pct, body_water_pct, muscle_mass_kg,
             bone_mass_kg, raw_json, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            day.isoformat(),
            _grams_to_kg(target.get("weight")),
            target.get("bodyFat"),
            target.get("bodyWater"),
            _grams_to_kg(target.get("muscleMass")),
            _grams_to_kg(target.get("boneMass")),
            json.dumps(payload),
            _now_iso(),
        ),
    )
    return True


INGESTERS: dict[str, Callable[[Garmin, sqlite3.Connection, date], bool]] = {
    "summary": ingest_daily_summary,
    "heart_rate": ingest_heart_rate,
    "sleep": ingest_sleep,
    "weight": ingest_weight,
}


def ingest_range(
    client: Garmin,
    conn: sqlite3.Connection,
    start: date,
    end: date,
    metrics: tuple[str, ...] = METRICS,
) -> int:
    """Ingest ``metrics`` for each date in ``[start, end]``. Returns rows upserted."""
    written = 0
    day = start
    while day <= end:
        for name in metrics:
            if INGESTERS[name](client, conn, day):
                written += 1
                logger.info("ingested %s for %s", name, day)
        conn.commit()
        day += timedelta(days=1)
    return written


def _parse_since(spec: str) -> int:
    if not spec.endswith("d") or not spec[:-1].isdigit():
        raise argparse.ArgumentTypeError(f"--since expects e.g. '30d', got {spec!r}")
    return int(spec[:-1])


def _parse_date(spec: str) -> date:
    try:
        return date.fromisoformat(spec)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _parse_metrics(spec: str) -> tuple[str, ...]:
    if spec == "all":
        return METRICS
    parts = tuple(p.strip() for p in spec.split(",") if p.strip())
    unknown = [p for p in parts if p not in METRICS]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown metric(s): {unknown}. Valid: {list(METRICS)}"
        )
    return parts


def _resolve_window(args: argparse.Namespace) -> tuple[date, date]:
    today = date.today()
    if args.date:
        return args.date, args.date
    if args.from_ or args.to:
        return args.from_, args.to
    if args.since is not None:
        return today - timedelta(days=args.since), today
    return today, today


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    parser = argparse.ArgumentParser(
        prog="fitme.ingest",
        description="Pull Garmin Connect data into the local fitme DB.",
    )
    parser.add_argument("--since", type=_parse_since, help="lookback window, e.g. 7d / 30d")
    parser.add_argument("--from", dest="from_", type=_parse_date, help="YYYY-MM-DD (inclusive)")
    parser.add_argument("--to", type=_parse_date, help="YYYY-MM-DD (inclusive)")
    parser.add_argument("--date", type=_parse_date, help="single day")
    parser.add_argument(
        "--metrics",
        type=_parse_metrics,
        default=METRICS,
        help="comma-separated subset or 'all' (default: all)",
    )
    args = parser.parse_args(argv)

    if (args.from_ and not args.to) or (args.to and not args.from_):
        parser.error("--from and --to must be used together")

    start, end = _resolve_window(args)
    if start > end:
        parser.error(f"empty range: {start} > {end}")

    try:
        client = get_client()
    except GarminAuthError as err:
        logger.error("%s", err)
        return 2

    logger.info("ingesting %s..%s metrics=%s", start, end, list(args.metrics))
    with connect() as conn:
        written = ingest_range(client, conn, start, end, args.metrics)
    logger.info("done. %d rows written.", written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
