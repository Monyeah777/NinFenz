package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ImportHistoryStoreTest {
    @Test
    fun recordsAndFindsByDigest() {
        val dir = Files.createTempDirectory("nf-import-history").toFile()
        val store = ImportHistoryStore(dir)
        store.record("abc", "a.md")
        store.record("def", "b.md")
        assertEquals("a.md", store.find("abc")?.name)
        assertEquals("b.md", store.find("def")?.name)
        assertNull(store.find("missing"))
    }

    @Test
    fun recentAndClear() {
        val dir = Files.createTempDirectory("nf-import-history-3").toFile()
        val store = ImportHistoryStore(dir)
        store.record("a", "a.md")
        store.record("b", "b.md")
        assertEquals(1, store.recent(1).size)
        assertEquals(2, store.recent().size)
        store.clear()
        assertEquals(0, store.recent().size)
    }

    @Test
    fun duplicateDigestUpdatesInsteadOfAppending() {
        val dir = Files.createTempDirectory("nf-import-history-2").toFile()
        val store = ImportHistoryStore(dir)
        store.record("abc", "first.md")
        store.record("abc", "second.md")
        assertEquals("second.md", store.find("abc")?.name)
    }
}
