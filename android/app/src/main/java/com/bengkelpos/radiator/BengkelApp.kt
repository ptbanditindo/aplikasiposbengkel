package com.bengkelpos.radiator

import android.app.Activity
import android.app.Application
import android.os.Bundle
import com.bengkelpos.radiator.backup.BackupScheduler
import com.bengkelpos.radiator.pin.PinSession
import com.bengkelpos.radiator.pin.PinSettings
import com.bengkelpos.radiator.pin.SystemLockoutClock
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform

class BengkelApp : Application() {

    override fun onCreate() {
        super.onCreate()
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }
        // Sesi latar belakang dipulihkan agar batas "Kunci otomatis" tetap
        // berlaku saat proses aplikasi sempat dimatikan sistem.
        val pinSettings = PinSettings(this)
        PinSession.restore(SystemLockoutClock, pinSettings)
        // WorkManager menyimpan jadwal di disk; daftarkan ulang setelah restart.
        BackupScheduler.ensureScheduled(this)
        registerActivityLifecycleCallbacks(object : ActivityLifecycleCallbacks {
            private var startedActivities = 0

            override fun onActivityStarted(activity: Activity) {
                startedActivities++
                ForegroundState.set(true)
            }

            override fun onActivityStopped(activity: Activity) {
                startedActivities = (startedActivities - 1).coerceAtLeast(0)
                ForegroundState.set(startedActivities > 0)
                if (startedActivities == 0) {
                    PinSession.markBackground(SystemLockoutClock, pinSettings)
                }
            }

            override fun onActivityCreated(activity: Activity, savedInstanceState: Bundle?) = Unit
            override fun onActivityResumed(activity: Activity) = Unit
            override fun onActivityPaused(activity: Activity) = Unit
            override fun onActivitySaveInstanceState(activity: Activity, outState: Bundle) = Unit
            override fun onActivityDestroyed(activity: Activity) = Unit
        })
    }
}
