package dev.ninfenz.mobile.data

import java.io.File
import java.security.MessageDigest

/** 双跑复现检查：逐字节比较两次导出，报告首个差异偏移与 sha256。 */
object ReproChecker {
    data class Report(
        val stable: Boolean,
        val lengthA: Int,
        val lengthB: Int,
        val firstDiff: Int?,
        val sha256A: String,
        val sha256B: String
    )

    fun check(a: File, b: File): Report {
        val bytesA = a.readBytes()
        val bytesB = b.readBytes()
        val firstDiff = firstDifference(bytesA, bytesB)
        return Report(
            stable = firstDiff == null,
            lengthA = bytesA.size,
            lengthB = bytesB.size,
            firstDiff = firstDiff,
            sha256A = sha256(bytesA),
            sha256B = sha256(bytesB)
        )
    }

    fun firstDifference(a: ByteArray, b: ByteArray): Int? {
        val limit = minOf(a.size, b.size)
        for (i in 0 until limit) {
            if (a[i] != b[i]) return i
        }
        return if (a.size != b.size) limit else null
    }

    fun sha256(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
}
