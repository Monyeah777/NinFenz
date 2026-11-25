package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ExportHistoryStoreTest {
    @Test
    fun recordsNewestFirstAndDeduplicatesPath() {
        val dir = Files.createTempDirectory("nf-export-history").toFile()
        val store = ExportHistoryStore(dir)
        val f1 = File(dir, "a.md").apply { writeText("a") }
        val f2 = File(dir, "b.md").apply { writeText("b") }
        store.record("md", f1, "sha1", true, "ok")
        store.record("md", f2, "sha2")
        store.record("md", f1, "sha3", false, "bad")
        val entries = store.load()
        assertEquals(2, entries.size)
        assertEquals("a.md", entries.first().name)
        assertEquals("sha3", entries.first().sha256)
        assertEquals(false, entries.first().ok)
        assertEquals("bad", entries.first().message)
        assertEquals(1L, entries.first().bytes)
    }

    @Test
    fun removeOnlyOneRecord() {
        val dir = Files.createTempDirectory("nf-export-history-remove").toFile()
        val store = ExportHistoryStore(dir)
        val f1 = File(dir, "a.md").apply { writeText("a") }
        val f2 = File(dir, "b.md").apply { writeText("b") }
        store.record("md", f1, "s1")
        store.record("md", f2, "s2")
        store.remove(f1.absolutePath)
        assertEquals(listOf("b.md"), store.load().map { it.name })
    }

    @Test
    fun clearRemovesHistory() {
        val dir = Files.createTempDirectory("nf-export-history-clear").toFile()
        val store = ExportHistoryStore(dir)
        store.record("md", File(dir, "a.md").apply { writeText("a") }, "sha")
        assertTrue(store.load().isNotEmpty())
        assertTrue(store.clear())
        assertEquals(0, store.load().size)
    }

    @Test
    fun capsAtTwentyAndIgnoresCorruptJson() {
        val dir = Files.createTempDirectory("nf-export-history-2").toFile()
        val store = ExportHistoryStore(dir)
        repeat(22) {
            val f = File(dir, "e$it.md").apply { writeText("x") }
            store.record("md", f, "s$it")
        }
        assertEquals(20, store.load().size)
        File(dir, "exports/history.json").writeText("{bad", Charsets.UTF_8)
        assertEquals(0, store.load().size)
    }
}
