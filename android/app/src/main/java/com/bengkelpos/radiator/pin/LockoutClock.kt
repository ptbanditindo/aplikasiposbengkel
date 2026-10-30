package com.bengkelpos.radiator.pin

import android.os.SystemClock

interface LockoutClock {
    fun elapsedRealtimeMs(): Long
    fun wallClockMs(): Long
}

object SystemLockoutClock : LockoutClock {
    override fun elapsedRealtimeMs(): Long = SystemClock.elapsedRealtime()

    override fun wallClockMs(): Long = System.currentTimeMillis()
}
