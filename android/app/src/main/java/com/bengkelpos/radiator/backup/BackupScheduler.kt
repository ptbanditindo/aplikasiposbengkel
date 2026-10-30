package com.bengkelpos.radiator.backup

import android.content.Context
import android.content.SharedPreferences
import androidx.work.BackoffPolicy
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.time.Instant
import java.time.ZonedDateTime
import java.util.concurrent.TimeUnit

/**
 * Menjadwalkan backup harian lewat WorkManager (bukan thread Python/WebView).
 *
 * WorkManager menyimpan pekerjaan di disk sehingga tetap berjalan saat aplikasi
 * di latar belakang atau setelah perangkat dimulai ulang. Pengaturan jam
 * disimpan di SharedPreferences agar [ensureScheduled] bisa dipanggil saat
 * aplikasi start tanpa membuka backend lebih dulu.
 */
object BackupScheduler {

    const val UNIQUE_NAME = "bengkel-scheduled-backup"
    private const val PREFS = "bengkel_scheduled_backup"
    private const val KEY_ENABLED = "enabled"
    private const val KEY_JAM = "jam"
    private const val KEY_SCHEDULED_JAM = "scheduled_jam"
    private const val KEY_LAST_AT = "last_attempt_at"
    private const val KEY_LAST_SUCCESS_AT = "last_success_at"
    private const val KEY_LAST_STATUS = "last_status"
    private const val KEY_LAST_MESSAGE = "last_message"

    data class BackupStatus(
        val lastAttemptAt: String?,
        val lastSuccessAt: String?,
        val lastStatus: String?,
        val lastMessage: String?,
    )

    fun sync(context: Context, enabled: Boolean, jam: String?) {
        val app = context.applicationContext
        val prefs = prefs(app)
        // Jam tidak valid tidak boleh mematikan backup lokal; pakai default.
        val normalized = BackupPolicy.normalizeJam(jam) ?: (21 to 0)
        val text = BackupPolicy.formatJam(normalized)
        prefs.edit()
            .putBoolean(KEY_ENABLED, enabled)
            .putString(KEY_JAM, text)
            .apply()
        if (!enabled) {
            cancel(app)
            return
        }
        enqueue(app, prefs, text)
    }

    /** Dipanggil saat aplikasi start; tidak menggeser jadwal yang sudah ada. */
    fun ensureScheduled(context: Context) {
        val app = context.applicationContext
        val prefs = prefs(app)
        // Backup lokal selalu terjadwal, termasuk saat Telegram tidak dipakai.
        val normalized =
            BackupPolicy.normalizeJam(prefs.getString(KEY_JAM, null)) ?: (21 to 0)
        val jam = BackupPolicy.formatJam(normalized)
        prefs.edit()
            .putBoolean(KEY_ENABLED, true)
            .putString(KEY_JAM, jam)
            .apply()
        enqueue(app, prefs, jam)
    }

    fun cancel(context: Context) {
        WorkManager.getInstance(context.applicationContext)
            .cancelUniqueWork(UNIQUE_NAME)
    }

    fun recordResult(context: Context, status: String, message: String) {
        val now = Instant.now().toString()
        val editor = prefs(context.applicationContext).edit()
            .putString(KEY_LAST_AT, now)
            .putString(KEY_LAST_STATUS, status)
            .putString(KEY_LAST_MESSAGE, message.take(300))
        if (status == "ok") {
            editor.putString(KEY_LAST_SUCCESS_AT, now)
        }
        editor.apply()
    }

    fun status(context: Context): BackupStatus {
        val prefs = prefs(context.applicationContext)
        return BackupStatus(
            lastAttemptAt = prefs.getString(KEY_LAST_AT, null),
            lastSuccessAt = prefs.getString(KEY_LAST_SUCCESS_AT, null),
            lastStatus = prefs.getString(KEY_LAST_STATUS, null),
            lastMessage = prefs.getString(KEY_LAST_MESSAGE, null),
        )
    }

    private fun enqueue(
        app: Context,
        prefs: SharedPreferences,
        jam: String,
    ) {
        val target = BackupPolicy.normalizeJam(jam) ?: return
        val delay = BackupPolicy.initialDelayMillis(
            ZonedDateTime.now(),
            target.first,
            target.second,
        )
        val request = PeriodicWorkRequestBuilder<ScheduledBackupWorker>(
            BackupPolicy.PERIOD_HOURS,
            TimeUnit.HOURS,
        )
            .setInitialDelay(delay, TimeUnit.MILLISECONDS)
            .setBackoffCriteria(
                BackoffPolicy.EXPONENTIAL,
                BackupPolicy.RETRY_MINUTES,
                TimeUnit.MINUTES,
            )
            .addTag(UNIQUE_NAME)
            .build()

        // KEEP saat jam sama agar membuka aplikasi tidak menunda jadwal terus.
        val policy = if (prefs.getString(KEY_SCHEDULED_JAM, null) == jam) {
            ExistingPeriodicWorkPolicy.KEEP
        } else {
            prefs.edit().putString(KEY_SCHEDULED_JAM, jam).apply()
            ExistingPeriodicWorkPolicy.CANCEL_AND_REENQUEUE
        }
        WorkManager.getInstance(app)
            .enqueueUniquePeriodicWork(UNIQUE_NAME, policy, request)
    }

    private fun prefs(context: Context): SharedPreferences =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
}
