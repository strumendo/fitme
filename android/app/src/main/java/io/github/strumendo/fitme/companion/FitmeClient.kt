package io.github.strumendo.fitme.companion

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import java.io.IOException
import java.util.concurrent.TimeUnit

@Serializable
data class SyncStateRow(
    @SerialName("data_type") val dataType: String,
    @SerialName("synced_at") val syncedAt: String,
    val rows: Int,
)

@Serializable
private data class StatusResponse(@SerialName("sync_state") val syncState: List<SyncStateRow>)

@Serializable
private data class SyncResponse(val ingested: Map<String, Int>)

@Serializable
private data class ErrorResponse(val error: String)

/** The receiver answered with an error status — not retryable by waiting. */
class ReceiverException(val status: Int, message: String) : Exception(message)

/**
 * Talks to `fitme.receiver` (`GET /samsung/status`, `POST /samsung/sync`).
 * Network failures surface as [IOException] (worth a retry); HTTP errors as
 * [ReceiverException].
 */
class FitmeClient(baseUrl: String, private val token: String) {
    private val base = baseUrl.trimEnd('/')
    private val http = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()

    suspend fun status(): List<SyncStateRow> = withContext(Dispatchers.IO) {
        val request = authorized("$base/samsung/status").get().build()
        http.newCall(request).execute().use { response ->
            PayloadJson.decodeFromString<StatusResponse>(bodyOrThrow(response)).syncState
        }
    }

    suspend fun sync(payload: Payload): Map<String, Int> = withContext(Dispatchers.IO) {
        val body = PayloadJson.encodeToString(Payload.serializer(), payload)
            .toRequestBody(JSON)
        val request = authorized("$base/samsung/sync").post(body).build()
        http.newCall(request).execute().use { response ->
            PayloadJson.decodeFromString<SyncResponse>(bodyOrThrow(response)).ingested
        }
    }

    private fun authorized(url: String): Request.Builder =
        Request.Builder().url(url).header("Authorization", "Bearer $token")

    private fun bodyOrThrow(response: Response): String {
        val text = response.body?.string().orEmpty()
        if (response.isSuccessful) return text
        val detail = runCatching { PayloadJson.decodeFromString<ErrorResponse>(text).error }
            .getOrDefault(text.take(200))
        throw ReceiverException(response.code, "HTTP ${response.code}: $detail")
    }

    private companion object {
        val JSON = "application/json".toMediaType()
    }
}
