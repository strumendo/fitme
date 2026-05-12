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

METRICS: tuple[str, ...] = (
    "summary",
    "heart_rate",
    "sleep",
    "weight",
    "body_battery",
    "stress",
    "hrv",
    "activities",
)
PER_DAY_METRICS: tuple[str, ...] = (
    "summary",
    "heart_rate",
    "sleep",
    "weight",
    "body_battery",
    "stress",
    "hrv",
)
RANGE_METRICS: tuple[str, ...] = ("activities",)


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


def ingest_body_battery(client: Garmin, conn: sqlite3.Connection, day: date) -> bool:
    try:
        payload = gconn.body_battery(client, day)
    except Exception:
        logger.exception("body_battery fetch failed for %s", day)
        return False
    entry = payload[0] if isinstance(payload, list) and payload else None
    if not isinstance(entry, dict):
        logger.info("no body_battery data for %s", day)
        return False
    values_array = entry.get("bodyBatteryValuesArray") or []
    levels = [pair[1] for pair in values_array if isinstance(pair, (list, tuple)) and len(pair) >= 2 and isinstance(pair[1], (int, float))]
    highest = max(levels) if levels else None
    lowest = min(levels) if levels else None
    conn.execute(
        """
        INSERT OR REPLACE INTO body_battery
            (date, charged, drained, highest, lowest, raw_json, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            day.isoformat(),
            entry.get("charged"),
            entry.get("drained"),
            highest,
            lowest,
            json.dumps(entry),
            _now_iso(),
        ),
    )
    return True


def _stress_bucket_seconds(payload: dict) -> tuple[int, int, int, int]:
    """Derive (rest, low, medium, high) seconds from the intraday stress array.

    Garmin's ``get_stress_data`` payload samples stress every 3 min as
    ``[timestamp_ms, level]`` pairs in ``stressValuesArray``. Negative levels
    are sentinels (-1 = asleep/resting, -2 = unmeasurable) so they're skipped.
    Buckets follow Garmin's UI: 0–25 rest, 26–50 low, 51–75 medium, 76–100 high.
    """
    arr = payload.get("stressValuesArray") or []
    if len(arr) < 2:
        return 0, 0, 0, 0
    interval = max(1, (arr[1][0] - arr[0][0]) // 1000)
    rest = low = medium = high = 0
    for entry in arr:
        if not isinstance(entry, (list, tuple)) or len(entry) < 2:
            continue
        level = entry[1]
        if not isinstance(level, (int, float)) or level < 0:
            continue
        if level <= 25:
            rest += interval
        elif level <= 50:
            low += interval
        elif level <= 75:
            medium += interval
        else:
            high += interval
    return rest, low, medium, high


def ingest_stress(client: Garmin, conn: sqlite3.Connection, day: date) -> bool:
    try:
        payload = gconn.stress(client, day)
    except Exception:
        logger.exception("stress fetch failed for %s", day)
        return False
    if not isinstance(payload, dict):
        logger.info("no stress data for %s", day)
        return False
    avg = payload.get("avgStressLevel")
    if avg is None:
        avg = payload.get("averageStressLevel")
    if avg in (None, -1):
        logger.info("no stress data for %s", day)
        return False
    rest_s, low_s, med_s, high_s = _stress_bucket_seconds(payload)
    conn.execute(
        """
        INSERT OR REPLACE INTO stress
            (date, avg_level, max_level, rest_seconds, low_seconds,
             medium_seconds, high_seconds, raw_json, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            day.isoformat(),
            avg,
            payload.get("maxStressLevel"),
            rest_s,
            low_s,
            med_s,
            high_s,
            json.dumps(payload),
            _now_iso(),
        ),
    )
    return True


def ingest_hrv(client: Garmin, conn: sqlite3.Connection, day: date) -> bool:
    try:
        payload = gconn.hrv(client, day)
    except Exception:
        logger.exception("hrv fetch failed for %s", day)
        return False
    if not isinstance(payload, dict):
        logger.info("no hrv data for %s", day)
        return False
    summary = payload.get("hrvSummary") or {}
    if not summary.get("lastNightAvg") and not summary.get("weeklyAvg"):
        logger.info("no hrv data for %s", day)
        return False
    conn.execute(
        """
        INSERT OR REPLACE INTO hrv
            (date, weekly_avg, last_night_avg, last_night_5min_high, status,
             raw_json, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            day.isoformat(),
            summary.get("weeklyAvg"),
            summary.get("lastNightAvg"),
            summary.get("lastNight5MinHigh"),
            summary.get("status"),
            json.dumps(payload),
            _now_iso(),
        ),
    )
    return True


def ingest_activities(
    client: Garmin, conn: sqlite3.Connection, start: date, end: date
) -> int:
    """Fetch activities in ``[start, end]`` and upsert each by ``activityId``.

    Returns the number of rows upserted. Range-based (unlike per-day ingesters)
    because the Garmin endpoint is range-native and avoids re-paginating per day.
    """
    try:
        payload = gconn.activities(client, start, end)
    except Exception:
        logger.exception("activities fetch failed for %s..%s", start, end)
        return 0
    if not isinstance(payload, list) or not payload:
        logger.info("no activities in %s..%s", start, end)
        return 0
    written = 0
    for item in payload:
        if not isinstance(item, dict):
            continue
        activity_id = item.get("activityId")
        start_time = item.get("startTimeLocal") or item.get("startTimeGMT")
        if activity_id is None or not start_time:
            continue
        type_key = (item.get("activityType") or {}).get("typeKey")
        conn.execute(
            """
            INSERT OR REPLACE INTO activities
                (activity_id, date, start_time, type, name, duration_s,
                 distance_m, calories_kcal, avg_hr_bpm, max_hr_bpm,
                 raw_json, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(activity_id),
                str(start_time)[:10],
                str(start_time),
                type_key,
                item.get("activityName"),
                int(item["duration"]) if isinstance(item.get("duration"), (int, float)) else None,
                item.get("distance"),
                item.get("calories"),
                int(item["averageHR"]) if isinstance(item.get("averageHR"), (int, float)) else None,
                int(item["maxHR"]) if isinstance(item.get("maxHR"), (int, float)) else None,
                json.dumps(item),
                _now_iso(),
            ),
        )
        written += 1
    return written


INGESTERS: dict[str, Callable[[Garmin, sqlite3.Connection, date], bool]] = {
    "summary": ingest_daily_summary,
    "heart_rate": ingest_heart_rate,
    "sleep": ingest_sleep,
    "weight": ingest_weight,
    "body_battery": ingest_body_battery,
    "stress": ingest_stress,
    "hrv": ingest_hrv,
}


def ingest_range(
    client: Garmin,
    conn: sqlite3.Connection,
    start: date,
    end: date,
    metrics: tuple[str, ...] = METRICS,
) -> int:
    """Ingest ``metrics`` for each date in ``[start, end]``. Returns rows upserted.

    Per-day metrics are looped day-by-day; range-native metrics (``activities``)
    are fetched once over the full window.
    """
    written = 0
    per_day = tuple(m for m in metrics if m in PER_DAY_METRICS)
    range_metrics = tuple(m for m in metrics if m in RANGE_METRICS)

    day = start
    while day <= end:
        for name in per_day:
            if INGESTERS[name](client, conn, day):
                written += 1
                logger.info("ingested %s for %s", name, day)
        conn.commit()
        day += timedelta(days=1)

    if "activities" in range_metrics:
        rows = ingest_activities(client, conn, start, end)
        if rows:
            logger.info("ingested %d activities in %s..%s", rows, start, end)
        written += rows
        conn.commit()

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
