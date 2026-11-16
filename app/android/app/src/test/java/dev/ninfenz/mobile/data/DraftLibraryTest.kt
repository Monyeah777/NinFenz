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
    fun deletesDraftAndMapping() {
        val dir = Files.createTempDirectory("nf-drafts-3").toFile()
        val drafts = java.io.File(dir, "drafts").apply { mkdirs() }
        val f = java.io.File(drafts, "a.json").apply { writeText("{}") }
        java.io.File(drafts, "a.mapping.json").writeText("{}")
        assertTrue(DraftLibrary.delete(f))
        assertTrue(!f.exists())
        assertTrue(!java.io.File(drafts, "a.mapping.json").exists())
    }

    @Test
    fun renamesDraftAndRejectsCollision() {
        val dir = Files.createTempDirectory("nf-drafts-4").toFile()
        val drafts = java.io.File(dir, "drafts").apply { mkdirs() }
        val f = java.io.File(drafts, "a.json").apply { writeText("{}") }
        java.io.File(drafts, "b.json").writeText("{}")
        val renamed = DraftLibrary.rename(f, "c")
        assertTrue(renamed.name == "c.json")
        assertTrue(runCatching { DraftLibrary.rename(renamed, "b") }.isFailure)
    }

    @Test
    fun missingDirectoryIsEmpty() {
        val dir = Files.createTempDirectory("nf-drafts-2").toFile()
        assertTrue(DraftLibrary.list(dir).isEmpty())
    }
}
