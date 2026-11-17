package dev.ninfenz.mobile.data

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FileAccessLimitTest {
    @Test
    fun readsWithinLimit() {
        val bytes = FileAccess.readLimited(ByteArrayInputStream(ByteArray(10) { 7 }), 10)
        assertEquals(10, bytes.size)
        assertEquals(7.toByte(), bytes[0])
    }

    @Test
    fun copiesWithinTreeBudget() {
        val out = ByteArrayOutputStream()
        FileAccess.copyLimited(ByteArrayInputStream(ByteArray(10)), out, 10, longArrayOf(10))
        assertEquals(10, out.size())
    }

    @Test
    fun rejectsTreeBudgetOverflow() {
        assertTrue(
            runCatching {
                FileAccess.copyLimited(ByteArrayInputStream(ByteArray(11)), ByteArrayOutputStream(), 100, longArrayOf(10))
            }.isFailure
        )
    }

    @Test
    fun rejectsOverLimit() {
        assertTrue(runCatching { FileAccess.readLimited(ByteArrayInputStream(ByteArray(11)), 10) }.isFailure)
    }
}
