package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class LibraryStoreTest {
    @Test
    fun uniqueDraftBaseAvoidsOverwritingExistingDraftAndSidecar() {
        val dir = Files.createTempDirectory("nf-library-store").toFile()
        val store = LibraryStore(dir)
        val first = store.uniqueDraftBase("note.md")
        assertEquals("note.md", first)
        store.saveDraft(first, "{}")
        store.saveDraft(first + ".mapping", "{}")

        val second = store.uniqueDraftBase("note.md")
        assertEquals("note.md-2", second)
        store.saveDraft(second, "{}")

        val third = store.uniqueDraftBase("note.md")
        assertEquals("note.md-3", third)
        assertTrue(store.draftsDir().listFiles()!!.any { it.name == "note.md.json" })
        assertTrue(store.draftsDir().listFiles()!!.any { it.name == "note.md-2.json" })
    }

    @Test
    fun uniqueDraftBaseSanitizesName() {
        val dir = Files.createTempDirectory("nf-library-store-2").toFile()
        val store = LibraryStore(dir)
        assertEquals("a_b_c", store.uniqueDraftBase("a b/c"))
    }
}
