package io.github.strumendo.fitme.companion

import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

/**
 * Glue between Samsung Health, the receiver and the file export. Both the UI
 * and [SyncWorker] go through here.
 */
class SyncRunner(private val context: Context, private val settings: Settings) {
    private val reader = SamsungHealthReader(context)

    /** Ask the receiver where each type left off, read the delta, push it. */
    suspend fun syncNow(): Map<String, Int> {
        check(settings.isConfigured) { "Configure a URL e o token primeiro" }
        val client = FitmeClient(settings.receiverUrl, settings.token)
        val syncedAt = client.status().associate { it.dataType to it.syncedAt }
        val payload = reader.read(windowsFromSyncState(syncedAt))
        val ingested = client.sync(payload)
        settings.lastResult = "Sync ${stamp()}: ${ingested.format()}"
        return ingested
    }

    /**
     * Write the last [EXPORT_DAYS] days to a JSON file in the app cache and
     * return a share intent (Drive, Downloads, e-mail…) for
     * `python -m fitme.samsung_import`.
     */
    suspend fun exportIntent(): Intent {
        val payload = reader.read(fixedWindows(EXPORT_DAYS))
        val file = withContext(Dispatchers.IO) {
            val dir = File(context.cacheDir, "exports").apply { mkdirs() }
            dir.listFiles()?.forEach { it.delete() }
            File(dir, "samsung-health-${stamp("yyyyMMdd-HHmm")}.json").apply {
                writeText(PayloadJson.encodeToString(Payload.serializer(), payload))
            }
        }
        settings.lastResult = "Export ${stamp()}: ${payload.counts().format()}"
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.exports", file)
        val send = Intent(Intent.ACTION_SEND)
            .setType("application/json")
            .putExtra(Intent.EXTRA_STREAM, uri)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        return Intent.createChooser(send, "Exportar JSON")
    }

    private fun Map<String, Int>.format(): String =
        entries.joinToString { (type, rows) -> "$type=$rows" }

    private fun stamp(pattern: String = "dd/MM HH:mm"): String =
        LocalDateTime.now().format(DateTimeFormatter.ofPattern(pattern))
}
