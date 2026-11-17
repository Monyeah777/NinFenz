package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ReproCheckerTest {
    private fun file(name: String, bytes: ByteArray) = Files.createTempDirectory("nf-repro").toFile().resolve(name).apply {
        writeBytes(bytes)
    }

    @Test
    fun identicalFilesAreStable() {
        val a = file("a.bin", byteArrayOf(1, 2, 3))
        val b = file("b.bin", byteArrayOf(1, 2, 3))
        val report = ReproChecker.check(a, b)
        assertTrue(report.stable)
        assertNull(report.firstDiff)
        assertEquals(report.sha256A, report.sha256B)
    }

    @Test
    fun reportsFirstDifferingOffset() {
        val a = file("a.bin", byteArrayOf(1, 2, 3, 4))
        val b = file("b.bin", byteArrayOf(1, 9, 3, 4))
        val report = ReproChecker.check(a, b)
        assertFalse(report.stable)
        assertEquals(1, report.firstDiff)
    }

    @Test
    fun reportsLengthDifferenceAtTail() {
        val report = ReproChecker.firstDifference(byteArrayOf(1, 2), byteArrayOf(1, 2, 3))
        assertEquals(2, report)
    }
}
