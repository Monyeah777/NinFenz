package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Test

class RecentProjectStoreTest {
    @Test
    fun recordMovesProjectToFrontAndDeduplicates() {
        val dir = Files.createTempDirectory("nf-recent").toFile()
        val store = RecentProjectStore(dir)
        assertEquals(emptyList<String>(), store.load())
        store.record("a")
        store.record("b")
        val after = store.record("a")
        assertEquals(listOf("a", "b"), after)
        assertEquals(listOf("a", "b"), store.load())
    }
}
