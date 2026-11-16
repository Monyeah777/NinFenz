package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class StorageStatsTest {
    @Test
    fun sumsDirectoriesAndClearsImportCache() {
        val root = Files.createTempDirectory("nf-storage").toFile()
        val files = File(root, "files").apply { mkdirs() }
        val cache = File(root, "cache").apply { mkdirs() }
        File(files, "projects").mkdirs(); File(files, "projects/p.json").writeText("1234")
        File(files, "drafts").mkdirs(); File(files, "drafts/d.json").writeText("12")
        File(files, "exports").mkdirs(); File(files, "exports/e.md").writeText("123")
        File(cache, "imports").mkdirs(); File(cache, "imports/a.tmp").writeText("1")
        File(cache, "shared").mkdirs(); File(cache, "shared/b.md").writeText("12")
        File(cache, "other").mkdirs(); File(cache, "other/keep").writeText("1")
        File(files, "library/packs").mkdirs(); File(files, "library/packs/p.json").writeText("12345")
        File(files, "projects-archive").mkdirs(); File(files, "projects-archive/a.archived").writeText("12")

        val stats = StorageStats.scan(files, cache)
        assertEquals(4, stats.projects)
        assertEquals(2, stats.drafts)
        assertEquals(3, stats.exports)
        assertEquals(4, stats.cache)
        assertEquals(5, stats.packs)
        assertEquals(2, stats.archives)
        assertEquals(20, stats.total)

        val removed = StorageStats.clearImportCache(cache)
        assertEquals(2, removed)
        assertTrue(!File(cache, "imports").exists())
        assertTrue(!File(cache, "shared").exists())
        assertTrue(File(cache, "other/keep").isFile)
    }

    @Test
    fun missingDirsAreZero() {
        val root = Files.createTempDirectory("nf-storage-2").toFile()
        assertEquals(0, StorageStats.scan(root, root).total)
    }
}
