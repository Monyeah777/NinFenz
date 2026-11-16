package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SearchHistoryStoreTest {
    @Test
    fun recordsMostRecentFirstAndDeduplicates() {
        val dir = Files.createTempDirectory("nf-search-history").toFile()
        val store = SearchHistoryStore(dir)
        store.record("alpha")
        store.record("beta")
        store.record("alpha")
        assertEquals(listOf("alpha", "beta"), store.load())
    }

    @Test
    fun capsAtTenAndClearWorks() {
        val dir = Files.createTempDirectory("nf-search-history-2").toFile()
        val store = SearchHistoryStore(dir)
        (1..12).forEach { store.record("q$it") }
        assertEquals(10, store.load().size)
        assertEquals("q12", store.load().first())
        store.clear()
        assertTrue(store.load().isEmpty())
    }
}
