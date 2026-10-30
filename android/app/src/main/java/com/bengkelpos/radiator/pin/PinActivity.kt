package com.bengkelpos.radiator.pin

import android.animation.ObjectAnimator
import android.app.AlertDialog
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.text.InputType
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import com.bengkelpos.radiator.MainActivity
import com.bengkelpos.radiator.R
import java.util.Locale
import java.util.concurrent.Executors

class PinActivity : AppCompatActivity() {

    private enum class Mode { CREATE, CONFIRM, UNLOCK }

    private lateinit var pinTitle: TextView
    private lateinit var pinSubtitle: TextView
    private lateinit var pinDots: LinearLayout
    private lateinit var pinMessage: TextView
    private lateinit var pinCountdown: TextView
    private lateinit var pinKeypad: LinearLayout
    private lateinit var pinForgot: Button

    private var store: PinStore? = null
    private var mode = Mode.UNLOCK
    private val entered = StringBuilder(PIN_LENGTH)
    private var firstPin: CharArray? = null
    private var dots: List<ImageView> = emptyList()
    private var busy = false
    private var lockedRemainingMs = 0L
    private var resetInProgress = false

    private val clock: LockoutClock = SystemLockoutClock
    private val mainHandler = Handler(Looper.getMainLooper())
    private val worker = Executors.newSingleThreadExecutor()

    private val countdownTick = object : Runnable {
        override fun run() {
            val current = store
            if (current == null || lockedRemainingMs <= 0L) return
            val state = current.clearExpiredLock(clock)
            lockedRemainingMs = state.remainingLockMs(clock.elapsedRealtimeMs(), clock.wallClockMs())
            if (lockedRemainingMs > 0L) {
                updateCountdown()
                mainHandler.postDelayed(this, 500L)
            } else {
                pinCountdown.visibility = View.GONE
                pinMessage.text = ""
                pinMessage.visibility = View.INVISIBLE
                pinForgot.visibility = View.VISIBLE
                setKeypadEnabled(true)
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        setContentView(R.layout.activity_pin)

        pinTitle = findViewById(R.id.pinTitle)
        pinSubtitle = findViewById(R.id.pinSubtitle)
        pinDots = findViewById(R.id.pinDots)
        pinMessage = findViewById(R.id.pinMessage)
        pinCountdown = findViewById(R.id.pinCountdown)
        pinKeypad = findViewById(R.id.pinKeypad)
        pinForgot = findViewById(R.id.pinForgot)

        buildDots()
        wireKeys()
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                // Saat layar PIN menumpuk di atas layar data, back tidak boleh membukanya.
                if (isTaskRoot) finish()
            }
        })

        store = try {
            PinStore.open(this)
        } catch (error: PinStorageException) {
            showStorageError()
            return
        }
        startGate()
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        setIntent(intent)
        refreshLockedState()
    }

    override fun onResume() {
        super.onResume()
        refreshLockedState()
    }

    override fun onPause() {
        super.onPause()
        mainHandler.removeCallbacks(countdownTick)
        if (!busy) {
            entered.setLength(0)
            updateDots()
        }
    }

    override fun onDestroy() {
        mainHandler.removeCallbacksAndMessages(null)
        worker.shutdownNow()
        entered.setLength(0)
        firstPin?.fill('\u0000')
        firstPin = null
        super.onDestroy()
    }

    private fun startGate() {
        val current = store ?: return
        if (!current.hasPin()) {
            beginCreate()
            return
        }
        mode = Mode.UNLOCK
        pinTitle.setText(R.string.pin_unlock_title)
        pinSubtitle.setText(R.string.pin_unlock_subtitle)
        pinForgot.visibility = View.VISIBLE
        refreshLockedState()
    }

    private fun refreshLockedState() {
        val current = store ?: return
        if (mode != Mode.UNLOCK || busy) return
        val state = current.clearExpiredLock(clock)
        lockedRemainingMs = state.remainingLockMs(clock.elapsedRealtimeMs(), clock.wallClockMs())
        if (lockedRemainingMs > 0L) {
            showLockedUi(showWrongMessage = false)
        } else {
            lockedRemainingMs = 0L
            pinCountdown.visibility = View.GONE
            setKeypadEnabled(true)
        }
    }

    private fun beginCreate() {
        mode = Mode.CREATE
        firstPin?.fill('\u0000')
        firstPin = null
        entered.setLength(0)
        updateDots()
        pinTitle.setText(R.string.pin_create_title)
        pinSubtitle.setText(R.string.pin_create_subtitle)
        pinForgot.visibility = View.GONE
        pinCountdown.visibility = View.GONE
        hideMessage()
        lockedRemainingMs = 0L
        setKeypadEnabled(true)
    }

    private fun buildDots() {
        pinDots.removeAllViews()
        val size = dp(14)
        val gap = dp(10)
        dots = List(PIN_LENGTH) {
            ImageView(this).apply {
                setImageResource(R.drawable.dot_empty)
                layoutParams = LinearLayout.LayoutParams(size, size).apply {
                    marginStart = gap
                    marginEnd = gap
                }
                pinDots.addView(this)
            }
        }
    }

    private fun wireKeys() {
        val digitKeys = mapOf(
            R.id.key0 to '0',
            R.id.key1 to '1',
            R.id.key2 to '2',
            R.id.key3 to '3',
            R.id.key4 to '4',
            R.id.key5 to '5',
            R.id.key6 to '6',
            R.id.key7 to '7',
            R.id.key8 to '8',
            R.id.key9 to '9',
        )
        digitKeys.forEach { (viewId, digit) ->
            findViewById<Button>(viewId).setOnClickListener { onDigit(digit) }
        }
        findViewById<Button>(R.id.keyDelete).setOnClickListener { onDelete() }
        pinForgot.setOnClickListener { confirmForgotPin() }
    }

    private fun onDigit(digit: Char) {
        if (busy || lockedRemainingMs > 0L) return
        if (entered.length >= PIN_LENGTH) return
        hideMessage()
        entered.append(digit)
        updateDots()
        if (entered.length == PIN_LENGTH) submit()
    }

    private fun onDelete() {
        if (busy || lockedRemainingMs > 0L) return
        if (entered.isEmpty()) return
        entered.deleteCharAt(entered.length - 1)
        updateDots()
        hideMessage()
    }

    private fun updateDots() {
        dots.forEachIndexed { index, dot ->
            dot.setImageResource(if (index < entered.length) R.drawable.dot_filled else R.drawable.dot_empty)
        }
    }

    private fun submit() {
        val current = store ?: return
        val pin = entered.toString().toCharArray()
        entered.setLength(0)
        busy = true
        setKeypadEnabled(false)
        hideMessage()
        when (mode) {
            Mode.CREATE -> handleCreate(pin)
            Mode.CONFIRM -> handleConfirm(current, pin)
            Mode.UNLOCK -> handleUnlock(current, pin)
        }
    }

    private fun handleCreate(pin: CharArray) {
        firstPin?.fill('\u0000')
        firstPin = pin
        mode = Mode.CONFIRM
        pinTitle.setText(R.string.pin_confirm_title)
        pinSubtitle.setText(R.string.pin_confirm_subtitle)
        busy = false
        updateDots()
        setKeypadEnabled(true)
    }

    private fun handleConfirm(current: PinStore, pin: CharArray) {
        val reference = firstPin
        val matches = reference != null && reference.contentEquals(pin)
        pin.fill('\u0000')
        if (!matches) {
            reference?.fill('\u0000')
            firstPin = null
            mode = Mode.CREATE
            pinTitle.setText(R.string.pin_create_title)
            pinSubtitle.setText(R.string.pin_create_subtitle)
            busy = false
            updateDots()
            signalWrongPin()
            showTransientMessage(getString(R.string.pin_mismatch))
            setKeypadEnabled(true)
            return
        }
        reference?.fill('\u0000')
        firstPin = null
        runOnWorker {
            val saved = runCatching { current.savePin(pin) }.isSuccess
            pin.fill('\u0000')
            runOnUi {
                busy = false
                if (!saved) {
                    mode = Mode.CREATE
                    pinTitle.setText(R.string.pin_create_title)
                    pinSubtitle.setText(R.string.pin_create_subtitle)
                    updateDots()
                    showTransientMessage(getString(R.string.pin_storage_error))
                    setKeypadEnabled(true)
                    return@runOnUi
                }
                if (resetInProgress) {
                    resetInProgress = false
                    showResetDoneDialog()
                } else {
                    proceedAfterUnlock(clearStack = false)
                }
            }
        }
    }

    private fun handleUnlock(current: PinStore, pin: CharArray) {
        runOnWorker {
            val verified = runCatching { current.verifyPin(pin) }.getOrDefault(false)
            pin.fill('\u0000')
            if (verified) {
                runCatching { current.resetFailures() }
                runOnUi {
                    busy = false
                    lockedRemainingMs = 0L
                    updateDots()
                    proceedAfterUnlock(clearStack = false)
                }
                return@runOnWorker
            }
            val state = runCatching { current.registerFailure(clock) }.getOrNull()
            val attempts = state?.failedAttempts ?: 0
            val remainingMs = state?.remainingLockMs(
                clock.elapsedRealtimeMs(),
                clock.wallClockMs(),
            ) ?: 0L
            runOnUi {
                busy = false
                updateDots()
                signalWrongPin()
                if (state == null) {
                    showTransientMessage(getString(R.string.pin_storage_error))
                    setKeypadEnabled(true)
                    return@runOnUi
                }
                if (remainingMs > 0L) {
                    lockedRemainingMs = remainingMs
                    showTransientMessage(getString(R.string.pin_wrong))
                    showLockedUi(showWrongMessage = true)
                } else {
                    val remainingAttempts = LockoutPolicy.remainingAttemptsBeforeLock(attempts)
                    showTransientMessage(
                        if (remainingAttempts > 0) {
                            getString(R.string.pin_wrong_remaining, remainingAttempts)
                        } else {
                            getString(R.string.pin_wrong)
                        },
                    )
                    setKeypadEnabled(true)
                }
            }
        }
    }

    private fun showLockedUi(showWrongMessage: Boolean) {
        setKeypadEnabled(false)
        pinForgot.visibility = View.VISIBLE
        if (showWrongMessage) {
            pinMessage.setText(R.string.pin_wrong)
            pinMessage.visibility = View.VISIBLE
        }
        updateCountdown()
        pinCountdown.visibility = View.VISIBLE
        mainHandler.removeCallbacks(countdownTick)
        mainHandler.postDelayed(countdownTick, 500L)
    }

    private fun updateCountdown() {
        pinCountdown.text = getString(
            R.string.pin_locked_countdown,
            formatDuration(lockedRemainingMs),
        )
        pinCountdown.visibility = View.VISIBLE
    }

    private fun setKeypadEnabled(enabled: Boolean) {
        for (rowIndex in 0 until pinKeypad.childCount) {
            val row = pinKeypad.getChildAt(rowIndex) as? ViewGroup ?: continue
            for (childIndex in 0 until row.childCount) {
                row.getChildAt(childIndex).isEnabled = enabled
            }
        }
        pinKeypad.alpha = if (enabled) 1f else 0.45f
    }

    private fun signalWrongPin() {
        val vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            getSystemService(VibratorManager::class.java)?.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            getSystemService(Vibrator::class.java)
        }
        if (vibrator != null && vibrator.hasVibrator()) {
            vibrator.vibrate(VibrationEffect.createOneShot(220L, VibrationEffect.DEFAULT_AMPLITUDE))
        }
        ObjectAnimator.ofFloat(pinDots, "translationX", 0f, 14f, -14f, 10f, -10f, 0f)
            .setDuration(320L)
            .start()
    }

    private fun showTransientMessage(text: String) {
        pinMessage.text = text
        pinMessage.visibility = View.VISIBLE
    }

    private fun hideMessage() {
        pinMessage.text = ""
        pinMessage.visibility = View.INVISIBLE
    }

    private fun proceedAfterUnlock(clearStack: Boolean) {
        PinSession.markUnlocked(clock)
        entered.setLength(0)
        firstPin?.fill('\u0000')
        firstPin = null
        if (clearStack) {
            startActivity(
                Intent(this, MainActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
                },
            )
        } else if (isTaskRoot) {
            startActivity(Intent(this, MainActivity::class.java))
        }
        finish()
    }

    private fun confirmForgotPin() {
        if (busy) return
        AlertDialog.Builder(this)
            .setTitle(R.string.forgot_title)
            .setMessage(R.string.forgot_warning)
            .setNegativeButton(R.string.cancel, null)
            .setPositiveButton(R.string.continue_label) { _, _ -> confirmTypedReset() }
            .show()
    }

    private fun confirmTypedReset() {
        val input = EditText(this).apply {
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS
            hint = getString(R.string.reset_type_hint)
            setSingleLine()
        }
        val container = FrameLayout(this).apply {
            setPadding(dp(20), dp(8), dp(20), 0)
            addView(input)
        }
        AlertDialog.Builder(this)
            .setTitle(R.string.reset_confirm_title)
            .setMessage(R.string.reset_confirm_message)
            .setView(container)
            .setNegativeButton(R.string.cancel, null)
            .setPositiveButton(R.string.reset_action) { _, _ ->
                if (input.text.toString() == RESET_KEYWORD) {
                    performReset()
                } else {
                    Toast.makeText(this, R.string.reset_type_hint, Toast.LENGTH_LONG).show()
                    mainHandler.post { confirmTypedReset() }
                }
            }
            .show()
    }

    private fun performReset() {
        busy = true
        mainHandler.removeCallbacks(countdownTick)
        setKeypadEnabled(false)
        pinCountdown.visibility = View.GONE
        hideMessage()
        runOnWorker {
            LocalDataResetter.reset(this)
            val reopened = runCatching { PinStore.open(this) }
            runOnUi {
                busy = false
                resetInProgress = true
                entered.setLength(0)
                firstPin?.fill('\u0000')
                firstPin = null
                val reopenedStore = reopened.getOrNull()
                if (reopenedStore == null) {
                    store = null
                    showStorageError()
                    return@runOnUi
                }
                store = reopenedStore
                beginCreate()
            }
        }
    }

    private fun showResetDoneDialog() {
        AlertDialog.Builder(this)
            .setTitle(R.string.reset_done_title)
            .setMessage(getString(R.string.reset_done) + "\n\n" + getString(R.string.restore_hint))
            .setCancelable(false)
            .setPositiveButton(R.string.ok) { _, _ -> proceedAfterUnlock(clearStack = true) }
            .show()
    }

    private fun showStorageError() {
        setKeypadEnabled(false)
        pinForgot.visibility = View.GONE
        pinCountdown.visibility = View.GONE
        AlertDialog.Builder(this)
            .setTitle(R.string.pin_storage_title)
            .setMessage(R.string.pin_storage_message)
            .setCancelable(false)
            .setNegativeButton(R.string.cancel) { _, _ -> finishAffinity() }
            .setPositiveButton(R.string.reset_action) { _, _ -> performReset() }
            .show()
    }

    private fun runOnWorker(block: () -> Unit) {
        runCatching { worker.execute(block) }
    }

    private fun runOnUi(block: () -> Unit) {
        mainHandler.post {
            if (!isFinishing && !isDestroyed) block()
        }
    }

    private fun formatDuration(remainingMs: Long): String {
        val totalSeconds = (remainingMs + 999L) / 1000L
        val hours = totalSeconds / 3600L
        val minutes = totalSeconds % 3600L / 60L
        val seconds = totalSeconds % 60L
        return if (hours > 0L) {
            String.format(Locale.US, "%d:%02d:%02d", hours, minutes, seconds)
        } else {
            String.format(Locale.US, "%02d:%02d", minutes, seconds)
        }
    }

    private fun dp(value: Int): Int =
        (value * resources.displayMetrics.density + 0.5f).toInt()

    companion object {
        const val PIN_LENGTH = 6
        private const val RESET_KEYWORD = "RESET"
    }
}
