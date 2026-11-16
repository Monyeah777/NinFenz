package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Test

class ExportHistoryStoreTest {
    @Test
    fun recordsNewestFirstAndDeduplicatesPath() {
        val dir = Files.createTempDirectory("nf-export-history").toFile()
        val store = ExportHistoryStore(dir)
        val f1 = File(dir, "a.md").apply { writeText("a") }
        val f2 = File(dir, "b.md").apply { writeText("b") }
        store.record("md", f1, "sha1")
        store.record("md", f2, "sha2")
        store.record("md", f1, "sha3")
        val entries = store.load()
        assertEquals(2, entries.size)
        assertEquals("a.md", entries.first().name)
        assertEquals("sha3", entries.first().sha256)
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
