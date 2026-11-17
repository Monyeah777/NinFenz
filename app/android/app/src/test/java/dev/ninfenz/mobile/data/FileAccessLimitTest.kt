package dev.ninfenz.mobile.data

import java.io.ByteArrayInputStream
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
    fun rejectsOverLimit() {
        assertTrue(runCatching { FileAccess.readLimited(ByteArrayInputStream(ByteArray(11)), 10) }.isFailure)
    }
}
