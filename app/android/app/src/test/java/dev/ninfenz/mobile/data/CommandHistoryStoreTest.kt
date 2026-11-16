package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Test

class CommandHistoryStoreTest {
    @Test
    fun recordsRecentFirstAndDeduplicates() {
        val dir = Files.createTempDirectory("nf-command-history").toFile()
        val store = CommandHistoryStore(dir)
        store.record("import")
        store.record("search")
        store.record("import")
        assertEquals(listOf("import", "search"), store.load())
    }

    @Test
    fun capsAtFive() {
        val dir = Files.createTempDirectory("nf-command-history-2").toFile()
        val store = CommandHistoryStore(dir)
        (1..7).forEach { store.record("c$it") }
        assertEquals(5, store.load().size)
        assertEquals("c7", store.load().first())
    }
}
