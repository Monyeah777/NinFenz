package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import java.util.zip.ZipFile
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BackupServiceTest {
    @Test
    fun backupContainsManifestAndSourceFiles() {
        val root = Files.createTempDirectory("nf-backup").toFile()
        File(root, "projects").mkdirs()
        File(root, "projects/p.nfproject.json").writeText("{\"schema\":\"nf-project/1\"}")
        File(root, "drafts").mkdirs()
        File(root, "drafts/a.md.json").writeText("draft")
        val created = BackupService.create(root, 123L)
        assertTrue(created.file.isFile)
        assertEquals(2, created.entries)
        ZipFile(created.file).use { zip ->
            val names = zip.entries().toList().map { it.name }
            assertTrue(names.contains("manifest.json"))
            assertTrue(names.contains("projects/p.nfproject.json"))
            assertTrue(names.contains("drafts/a.md.json"))
            val manifest = zip.getInputStream(zip.getEntry("manifest.json")).bufferedReader().readText()
            assertTrue(manifest.contains("nf-backup/1"))
            assertTrue(manifest.contains("projects/p.nfproject.json"))
        }
    }

    @Test
    fun emptyBackupStillHasManifest() {
        val root = Files.createTempDirectory("nf-backup-2").toFile()
        val created = BackupService.create(root, 456L)
        assertEquals(0, created.entries)
        ZipFile(created.file).use { zip ->
            assertEquals(listOf("manifest.json"), zip.entries().toList().map { it.name })
        }
    }
}
