package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CrashLogStoreTest {
    @Test
    fun recordsAndReadsLastCrash() {
        val dir = Files.createTempDirectory("nf-crash").toFile()
        val store = CrashLogStore(dir)
        store.record(IllegalStateException("boom"))
        val text = store.read()!!
        assertTrue(text.contains("IllegalStateException"))
        assertTrue(text.contains("boom"))
        store.clear()
        assertNull(store.read())
    }

    @Test
    fun capsLargeStack() {
        val dir = Files.createTempDirectory("nf-crash-2").toFile()
        val store = CrashLogStore(dir)
        store.record(RuntimeException("x".repeat(100_000)))
        assertTrue(store.read()!!.length <= 64 * 1024 + 32)
    }
}
