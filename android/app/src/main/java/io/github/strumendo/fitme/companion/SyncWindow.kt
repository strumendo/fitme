package io.github.strumendo.fitme.companion

import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeParseException

/** Data types in the payload, same names as the fitme `sh_sync_state.data_type`. */
val DATA_TYPES = listOf(
    "steps_daily",
    "heart_rate_daily",
    "sleep",
    "body_composition",
    "nutrition",
    "water",
    "exercise",
)

/** First sync (nothing in `sh_sync_state` yet) reaches this far back. */
const val INITIAL_BACKFILL_DAYS = 90L

/** Re-read this many days before the last sync so late edits in Samsung Health still land. */
const val LATE_EDIT_MARGIN_DAYS = 2L

/** File export always covers a fixed window — the ingest side is idempotent. */
const val EXPORT_DAYS = 30L

data class ReadWindow(val start: LocalDateTime, val end: LocalDateTime)

/**
 * Per-type read window from the server's `sh_sync_state`: start of the day of
 * the last sync minus [LATE_EDIT_MARGIN_DAYS], or [INITIAL_BACKFILL_DAYS] back
 * when the type was never synced. Always ends now.
 */
fun windowsFromSyncState(
    syncedAt: Map<String, String>,
    now: LocalDateTime = LocalDateTime.now(),
    zone: ZoneId = ZoneId.systemDefault(),
): Map<String, ReadWindow> = DATA_TYPES.associateWith { type ->
    val last = syncedAt[type]?.let { parseLocalDate(it, zone) }
    val startDay = last?.minusDays(LATE_EDIT_MARGIN_DAYS)
        ?: now.toLocalDate().minusDays(INITIAL_BACKFILL_DAYS)
    ReadWindow(startDay.atStartOfDay(), now)
}

fun fixedWindows(days: Long, now: LocalDateTime = LocalDateTime.now()): Map<String, ReadWindow> {
    val start = now.toLocalDate().minusDays(days).atStartOfDay()
    return DATA_TYPES.associateWith { ReadWindow(start, now) }
}

private fun parseLocalDate(value: String, zone: ZoneId): LocalDate? = try {
    OffsetDateTime.parse(value).atZoneSameInstant(zone).toLocalDate()
} catch (_: DateTimeParseException) {
    null
}
