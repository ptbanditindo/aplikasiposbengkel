package com.bengkelpos.radiator.pin

/**
 * Keyboard Android tidak selalu memaksa huruf besar walau inputType meminta
 * CAP_CHARACTERS, jadi konfirmasi reset tidak boleh peka huruf besar/kecil.
 */
object PinResetKeyword {
    const val KEYWORD = "RESET"

    fun matches(input: CharSequence?): Boolean =
        input != null && input.toString().trim().equals(KEYWORD, ignoreCase = true)
}
