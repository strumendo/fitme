package io.github.strumendo.fitme.companion

import android.content.Context
import androidx.core.content.edit

/**
 * Receiver URL + token and the outcome of the last run, in plain
 * SharedPreferences (single-user personal app).
 */
class Settings(context: Context) {
    private val prefs = context.getSharedPreferences("fitme", Context.MODE_PRIVATE)

    var receiverUrl: String
        get() = prefs.getString(KEY_URL, "").orEmpty()
        set(value) = prefs.edit { putString(KEY_URL, value.trim()) }

    var token: String
        get() = prefs.getString(KEY_TOKEN, "").orEmpty()
        set(value) = prefs.edit { putString(KEY_TOKEN, value.trim()) }

    var periodicSync: Boolean
        get() = prefs.getBoolean(KEY_PERIODIC, false)
        set(value) = prefs.edit { putBoolean(KEY_PERIODIC, value) }

    var lastResult: String
        get() = prefs.getString(KEY_LAST_RESULT, "").orEmpty()
        set(value) = prefs.edit { putString(KEY_LAST_RESULT, value) }

    val isConfigured: Boolean
        get() = receiverUrl.isNotBlank() && token.isNotBlank()

    private companion object {
        const val KEY_URL = "receiver_url"
        const val KEY_TOKEN = "token"
        const val KEY_PERIODIC = "periodic_sync"
        const val KEY_LAST_RESULT = "last_result"
    }
}
