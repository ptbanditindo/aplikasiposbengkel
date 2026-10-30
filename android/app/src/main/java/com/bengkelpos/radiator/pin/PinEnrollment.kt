package com.bengkelpos.radiator.pin

/**
 * Menentukan PIN yang boleh disimpan setelah layar konfirmasi.
 * Array yang dikembalikan sengaja tidak dibersihkan: pemanggil wajib
 * menyimpannya lebih dulu, baru kemudian mengosongkan memorinya.
 */
object PinEnrollment {
    fun confirmedPin(firstPin: CharArray?, confirmation: CharArray): CharArray? =
        if (firstPin != null && firstPin.contentEquals(confirmation)) confirmation else null
}
