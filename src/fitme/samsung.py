"""Ingest Samsung Health data pushed by the companion Android app.

Samsung Health has no web API, so the phone reads the data through the
Samsung Health Data SDK and hands fitme a versioned JSON payload — over HTTP
(``fitme.receiver``) or as a file (``fitme.samsung_import``). Both paths end
in ``ingest_payload``; this module never touches the network.

Payload (``schema_version: 1``) — one optional array per data type::

    {
      "schema_version": 1,
      "steps_daily":      [{"date", "steps", "device_group"}],
      "heart_rate_daily": [{"date", "min", "max", "avg", "device_group"}],
      "sleep":            [{"uid", "start_time", "end_time", "duration_s",
                            "sleep_score", "awake_s", "light_s", "deep_s",
                            "rem_s", "device_group"}],
      "body_composition": [{"uid", "start_time", "weight_kg", "body_fat_pct",
                            "skeletal_muscle_mass_kg", "muscle_mass_pct",
                            "bmr_kcal", "total_body_water_l", "bmi",
                            "device_group"}],
      "nutrition":        [{"uid", "start_time", "title", "meal_type", "kcal",
                            "protein_g", "carbs_g", "fat_g", "device_group"}],
      "water":            [{"uid", "start_time", "amount_ml", "device_group"}],
      "exercise":         [{"uid", "start_time", "end_time", "exercise_type",
                            "custom_title", "duration_s", "kcal", "distance_m",
                            "mean_hr", "max_hr", "device_group"}]
    }

``start_time`` / ``end_time`` are ISO-8601 carrying the record's zone offset
(``2026-09-28T07:12:00-03:00``); the local ``date`` column is derived from
them. A type that is absent from the payload is left untouched; an empty
array still stamps ``sh_sync_state`` (the phone looked and found nothing).
Extra fields are kept in ``raw_json`` only. See
``docs/samsung-payload.example.json`` for a full example.

Idempotent: daily aggregates upsert by ``date``, everything else by the
Samsung ``uid``. A bad record is logged and skipped — it never sinks the batch.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import date, datetime, timezone
from typing import Callable

logger = logging.getLogger(__name__)

PAYLOAD_SCHEMA_VERSION = 1
DATA_TYPES: tuple[str, ...] = (
    "steps_daily",
    "heart_rate_daily",
    "sleep",
    "body_composition",
    "nutrition",
    "water",
    "exercise",
)


class PayloadError(ValueError):
    """The payload as a whole is unusable (wrong shape or schema version)."""


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _num(record: dict, key: str) -> int | float | None:
    value = record.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return None


def _text(record: dict, key: str) -> str | None:
    value = record.get(key)
    return value if isinstance(value, str) else None


def _required_text(record: dict, key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing or invalid {key!r}")
    return value


def _day(record: dict) -> str:
    return date.fromisoformat(_required_text(record, "date")).isoformat()


def _local_date(record: dict, key: str) -> str:
    """Local calendar date of an ISO timestamp (the offset is already applied)."""
    return datetime.fromisoformat(_required_text(record, key)).date().isoformat()


def _upsert_steps_daily(conn: sqlite3.Connection, record: dict, now: str) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO sh_steps_daily
            (date, steps, device_group, raw_json, fetched_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            _day(record),
            _num(record, "steps"),
            _text(record, "device_group"),
            json.dumps(record),
            now,
        ),
    )


def _upsert_heart_rate_daily(conn: sqlite3.Connection, record: dict, now: str) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO sh_heart_rate_daily
            (date, min_bpm, max_bpm, avg_bpm, device_group, raw_json, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _day(record),
            _num(record, "min"),
            _num(record, "max"),
            _num(record, "avg"),
            _text(record, "device_group"),
            json.dumps(record),
            now,
        ),
    )


def _upsert_sleep(conn: sqlite3.Connection, record: dict, now: str) -> None:
    # Keyed to the wake-up day, like Garmin's ``sleep.date``, so both sources
    # line up on the same calendar day.
    conn.execute(
        """
        INSERT OR REPLACE INTO sh_sleep
            (uid, date, start_time, end_time, total_seconds, sleep_score,
             awake_seconds, light_seconds, deep_seconds, rem_seconds,
             device_group, raw_json, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _required_text(record, "uid"),
            _local_date(record, "end_time"),
            _required_text(record, "start_time"),
            _required_text(record, "end_time"),
            _num(record, "duration_s"),
            _num(record, "sleep_score"),
            _num(record, "awake_s"),
            _num(record, "light_s"),
            _num(record, "deep_s"),
            _num(record, "rem_s"),
            _text(record, "device_group"),
            json.dumps(record),
            now,
        ),
    )


def _upsert_body_composition(conn: sqlite3.Connection, record: dict, now: str) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO sh_body_composition
            (uid, date, start_time, weight_kg, body_fat_pct,
             skeletal_muscle_mass_kg, muscle_mass_pct, bmr_kcal,
             total_body_water_l, bmi, device_group, raw_json, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _required_text(record, "uid"),
            _local_date(record, "start_time"),
            _required_text(record, "start_time"),
            _num(record, "weight_kg"),
            _num(record, "body_fat_pct"),
            _num(record, "skeletal_muscle_mass_kg"),
            _num(record, "muscle_mass_pct"),
            _num(record, "bmr_kcal"),
            _num(record, "total_body_water_l"),
            _num(record, "bmi"),
            _text(record, "device_group"),
            json.dumps(record),
            now,
        ),
    )


def _upsert_nutrition(conn: sqlite3.Connection, record: dict, now: str) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO sh_nutrition
            (uid, date, start_time, title, meal_type, kcal, protein_g,
             carbs_g, fat_g, device_group, raw_json, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _required_text(record, "uid"),
            _local_date(record, "start_time"),
            _required_text(record, "start_time"),
            _text(record, "title"),
            _text(record, "meal_type"),
            _num(record, "kcal"),
            _num(record, "protein_g"),
            _num(record, "carbs_g"),
            _num(record, "fat_g"),
            _text(record, "device_group"),
            json.dumps(record),
            now,
        ),
    )


def _upsert_water(conn: sqlite3.Connection, record: dict, now: str) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO sh_water
            (uid, date, start_time, amount_ml, device_group, raw_json, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _required_text(record, "uid"),
            _local_date(record, "start_time"),
            _required_text(record, "start_time"),
            _num(record, "amount_ml"),
            _text(record, "device_group"),
            json.dumps(record),
            now,
        ),
    )


def _upsert_exercise(conn: sqlite3.Connection, record: dict, now: str) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO sh_exercise
            (uid, date, start_time, end_time, exercise_type, custom_title,
             duration_s, kcal, distance_m, mean_hr, max_hr, device_group,
             raw_json, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _required_text(record, "uid"),
            _local_date(record, "start_time"),
            _required_text(record, "start_time"),
            _text(record, "end_time"),
            _text(record, "exercise_type"),
            _text(record, "custom_title"),
            _num(record, "duration_s"),
            _num(record, "kcal"),
            _num(record, "distance_m"),
            _num(record, "mean_hr"),
            _num(record, "max_hr"),
            _text(record, "device_group"),
            json.dumps(record),
            now,
        ),
    )


_UPSERTS: dict[str, Callable[[sqlite3.Connection, dict, str], None]] = {
    "steps_daily": _upsert_steps_daily,
    "heart_rate_daily": _upsert_heart_rate_daily,
    "sleep": _upsert_sleep,
    "body_composition": _upsert_body_composition,
    "nutrition": _upsert_nutrition,
    "water": _upsert_water,
    "exercise": _upsert_exercise,
}


def validate_payload(payload: object) -> dict:
    """Check the envelope; raise ``PayloadError`` if the batch is unusable.

    Only the shape is validated here — individual records are checked (and
    skipped when bad) during ingest.
    """
    if not isinstance(payload, dict):
        raise PayloadError("payload must be a JSON object")
    version = payload.get("schema_version")
    if version != PAYLOAD_SCHEMA_VERSION:
        raise PayloadError(
            f"unsupported schema_version {version!r} (expected {PAYLOAD_SCHEMA_VERSION})"
        )
    for data_type in DATA_TYPES:
        if data_type in payload and not isinstance(payload[data_type], list):
            raise PayloadError(f"{data_type!r} must be an array")
    return payload


def ingest_payload(conn: sqlite3.Connection, payload: object) -> dict[str, int]:
    """Upsert every record in ``payload``; return rows written per data type.

    Only the types present in the payload show up in the result (and get their
    ``sh_sync_state`` row stamped).
    """
    data = validate_payload(payload)
    now = _now_iso()
    counts: dict[str, int] = {}
    for data_type in DATA_TYPES:
        if data_type not in data:
            continue
        upsert = _UPSERTS[data_type]
        written = 0
        for record in data[data_type]:
            try:
                if not isinstance(record, dict):
                    raise TypeError("record must be a JSON object")
                upsert(conn, record, now)
            except (TypeError, ValueError, sqlite3.Error) as err:
                logger.warning("skipping %s record: %s", data_type, err)
                continue
            written += 1
        conn.execute(
            "INSERT OR REPLACE INTO sh_sync_state (data_type, synced_at, rows) "
            "VALUES (?, ?, ?)",
            (data_type, now, written),
        )
        counts[data_type] = written
    return counts
