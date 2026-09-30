package io.github.strumendo.fitme.companion

import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZoneOffset

class SyncWindowTest {
    private val zone = ZoneId.of("America/Sao_Paulo")
    private val now = LocalDateTime.of(2026, 9, 30, 12, 0)

    @Test
    fun neverSyncedTypeBackfills() {
        val windows = windowsFromSyncState(emptyMap(), now, zone)
        assertEquals(DATA_TYPES.toSet(), windows.keys)
        assertEquals(LocalDateTime.of(2026, 7, 2, 0, 0), windows.getValue("sleep").start)
        assertEquals(now, windows.getValue("sleep").end)
    }

    @Test
    fun syncedTypeRereadsLateEditMargin() {
        // 01:30 UTC on the 29th is still the 28th in São Paulo.
        val windows = windowsFromSyncState(mapOf("water" to "2026-09-29T01:30:00+00:00"), now, zone)
        assertEquals(LocalDateTime.of(2026, 9, 26, 0, 0), windows.getValue("water").start)
    }

    @Test
    fun unparseableSyncedAtFallsBackToBackfill() {
        val windows = windowsFromSyncState(mapOf("water" to "yesterday"), now, zone)
        assertEquals(LocalDateTime.of(2026, 7, 2, 0, 0), windows.getValue("water").start)
    }

    @Test
    fun isoWithOffsetKeepsRecordOffsetAndSeconds() {
        val instant = Instant.parse("2026-09-28T10:12:00Z")
        assertEquals(
            "2026-09-28T07:12:00-03:00",
            isoWithOffset(instant, ZoneOffset.ofHours(-3)),
        )
    }
}
