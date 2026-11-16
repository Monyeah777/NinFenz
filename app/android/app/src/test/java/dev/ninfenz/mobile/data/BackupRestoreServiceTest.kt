package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BackupRestoreServiceTest {
    @Test
    fun inspectsAndRestoresValidBackup() {
        val src = Files.createTempDirectory("nf-restore-src").toFile()
        File(src, "projects").mkdirs()
        File(src, "projects/p.nfproject.json").writeText("{\"schema\":\"nf-project/1\"}")
        File(src, "drafts").mkdirs()
        File(src, "drafts/a.md.json").writeText("draft")
        val created = BackupService.create(src, 789L)
        val checked = BackupRestoreService.inspect(created.file)
        assertTrue(checked.error ?: "", checked.ok)
        assertEquals(2, checked.entries.size)

        val dst = Files.createTempDirectory("nf-restore-dst").toFile()
        val restored = BackupRestoreService.restore(created.file, dst)
        assertEquals(2, restored.files)
        assertTrue(restored.snapshot?.isFile == true)
        assertEquals("draft", File(dst, "drafts/a.md.json").readText())
    }

    @Test
    fun rejectsPathTraversalEntry() {
        val dir = Files.createTempDirectory("nf-restore-bad").toFile()
        val bad = File(dir, "bad.zip")
        ZipOutputStream(bad.outputStream()).use { out ->
            val manifest = "{\"schema\":\"nf-backup/1\",\"files\":[{\"path\":\"../evil.txt\",\"bytes\":1,\"sha256\":\"x\"}]}"
            out.putNextEntry(ZipEntry("manifest.json")); out.write(manifest.toByteArray()); out.closeEntry()
        }
        assertFalse(BackupRestoreService.inspect(bad).ok)
    }

    @Test
    fun rejectsWrongSha() {
        val dir = Files.createTempDirectory("nf-restore-sha").toFile()
        val bad = File(dir, "bad.zip")
        ZipOutputStream(bad.outputStream()).use { out ->
            val data = "hello".toByteArray()
            val manifest = "{\"schema\":\"nf-backup/1\",\"files\":[{\"path\":\"projects/a\",\"bytes\":5,\"sha256\":\"deadbeef\"}]}"
            out.putNextEntry(ZipEntry("manifest.json")); out.write(manifest.toByteArray()); out.closeEntry()
            out.putNextEntry(ZipEntry("projects/a")); out.write(data); out.closeEntry()
        }
        assertFalse(BackupRestoreService.inspect(bad).ok)
    }
}
