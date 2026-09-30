package io.github.strumendo.fitme.companion

import android.content.Context
import android.util.Log
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.io.IOException
import java.util.concurrent.TimeUnit

/** Periodic background sync: every 6h, only on an unmetered (Wi-Fi) network. */
class SyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val settings = Settings(applicationContext)
        if (!settings.isConfigured) return Result.success()
        return try {
            SyncRunner(applicationContext, settings).syncNow()
            Result.success()
        } catch (e: IOException) {
            // Phone off the home Wi-Fi, receiver down — try again later.
            Log.w(TAG, "periodic sync failed, will retry", e)
            settings.lastResult = "Falhou (rede): ${e.message}"
            Result.retry()
        } catch (e: Exception) {
            Log.e(TAG, "periodic sync failed", e)
            settings.lastResult = "Falhou: ${e.message}"
            Result.failure()
        }
    }

    companion object {
        private const val TAG = "SyncWorker"
        private const val WORK_NAME = "fitme-periodic-sync"

        fun schedule(context: Context) {
            val request = PeriodicWorkRequestBuilder<SyncWorker>(6, TimeUnit.HOURS)
                .setConstraints(
                    Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.UNMETERED)
                        .build()
                )
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.UPDATE,
                request,
            )
        }

        fun cancel(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME)
        }
    }
}
