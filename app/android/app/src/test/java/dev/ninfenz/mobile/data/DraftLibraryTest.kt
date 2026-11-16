package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DraftLibraryTest {
    @Test
    fun listsOnlyRealDrafts() {
        val dir = Files.createTempDirectory("nf-drafts").toFile()
        val drafts = java.io.File(dir, "drafts").apply { mkdirs() }
        java.io.File(drafts, "a.json").writeText("{}")
        java.io.File(drafts, "b.json").writeText("{}")
        java.io.File(drafts, "a.mapping.json").writeText("{}")
        java.io.File(drafts, "import-last.json").writeText("{}")
        java.io.File(drafts, "import-history.json").writeText("[]")
        assertEquals(setOf("a.json", "b.json"), DraftLibrary.list(dir).map { it.name }.toSet())
        assertTrue(DraftLibrary.read(java.io.File(drafts, "a.json")) == "{}")
    }

    @Test
    fun missingDirectoryIsEmpty() {
        val dir = Files.createTempDirectory("nf-drafts-2").toFile()
        assertTrue(DraftLibrary.list(dir).isEmpty())
    }
}
