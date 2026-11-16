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
        File(src, "projects-archive").mkdirs()
        File(src, "projects-archive/old.nfproject.json.1.archived").writeText("archived")
        File(src, "pack-trust.json").writeText("trust")
        val created = BackupService.create(src, 789L)
        val checked = BackupRestoreService.inspect(created.file)
        assertTrue(checked.error ?: "", checked.ok)
        assertEquals(4, checked.entries.size)

        val dst = Files.createTempDirectory("nf-restore-dst").toFile()
        val restored = BackupRestoreService.restore(created.file, dst)
        assertEquals(4, restored.files)
        assertTrue(restored.snapshot?.isFile == true)
        assertTrue(File(dst, "pack-trust.json").isFile)
        assertEquals("archived", File(dst, "projects-archive/old.nfproject.json.1.archived").readText())
        assertEquals("draft", File(dst, "drafts/a.md.json").readText())
    }

    @Test
    fun remembersLastSnapshotForRollback() {
        val src = Files.createTempDirectory("nf-restore-rollback-src").toFile()
        File(src, "projects").mkdirs()
        File(src, "projects/new.json").writeText("new")
        val backup = BackupService.create(src, 999L).file

        val dst = Files.createTempDirectory("nf-restore-rollback-dst").toFile()
        File(dst, "projects").mkdirs()
        File(dst, "projects/old.json").writeText("old")
        BackupRestoreService.restore(backup, dst)
        assertTrue(File(dst, "projects/new.json").isFile)

        val snapshot = BackupRestoreService.lastSnapshot(dst)
        assertTrue(snapshot != null && snapshot!!.isFile)
        BackupRestoreService.restore(snapshot!!, dst)
        assertEquals("old", File(dst, "projects/old.json").readText())
    }

    @Test
    fun rejectsUnlistedExtraEntry() {
        val dir = Files.createTempDirectory("nf-restore-extra").toFile()
        val bad = File(dir, "bad.zip")
        val data = "hello".toByteArray()
        val sha = ProjectPackage.sha256(data)
        ZipOutputStream(bad.outputStream()).use { out ->
            val manifest = "{\"schema\":\"nf-backup/1\",\"files\":[{\"path\":\"projects/a\",\"bytes\":5,\"sha256\":\"" + sha + "\"}]}"
            out.putNextEntry(ZipEntry("manifest.json")); out.write(manifest.toByteArray()); out.closeEntry()
            out.putNextEntry(ZipEntry("projects/a")); out.write(data); out.closeEntry()
            out.putNextEntry(ZipEntry("extra.txt")); out.write("x".toByteArray()); out.closeEntry()
        }
        assertFalse(BackupRestoreService.inspect(bad).ok)
    }

    @Test
    fun rejectsManifestMissingSha() {
        val dir = Files.createTempDirectory("nf-restore-nosha").toFile()
        val bad = File(dir, "bad.zip")
        ZipOutputStream(bad.outputStream()).use { out ->
            val manifest = "{\"schema\":\"nf-backup/1\",\"files\":[{\"path\":\"projects/a\",\"bytes\":5}]}"
            out.putNextEntry(ZipEntry("manifest.json")); out.write(manifest.toByteArray()); out.closeEntry()
            out.putNextEntry(ZipEntry("projects/a")); out.write("hello".toByteArray()); out.closeEntry()
        }
        assertFalse(BackupRestoreService.inspect(bad).ok)
    }

    @Test
    fun acceptsManifestWithBom() {
        val dir = Files.createTempDirectory("nf-restore-bom").toFile()
        val good = File(dir, "bom.zip")
        val data = "hello".toByteArray()
        val sha = ProjectPackage.sha256(data)
        ZipOutputStream(good.outputStream()).use { out ->
            val manifest = "\uFEFF" + "{\"schema\":\"nf-backup/1\",\"files\":[{\"path\":\"projects/a\",\"bytes\":5,\"sha256\":\"" + sha + "\"}]}"
            out.putNextEntry(ZipEntry("manifest.json")); out.write(manifest.toByteArray()); out.closeEntry()
            out.putNextEntry(ZipEntry("projects/a")); out.write(data); out.closeEntry()
        }
        assertTrue(BackupRestoreService.inspect(good).error ?: "", BackupRestoreService.inspect(good).ok)
    }

    @Test
    fun rejectsOversizedDeclaredTotal() {
        val dir = Files.createTempDirectory("nf-restore-total").toFile()
        val bad = File(dir, "bad.zip")
        ZipOutputStream(bad.outputStream()).use { out ->
            val manifest = "{\"schema\":\"nf-backup/1\",\"files\":[{\"path\":\"projects/a\",\"bytes\":600000000,\"sha256\":\"x\"}]}"
            out.putNextEntry(ZipEntry("manifest.json")); out.write(manifest.toByteArray()); out.closeEntry()
        }
        assertFalse(BackupRestoreService.inspect(bad).ok)
    }

    @Test
    fun rejectsOversizedSingleEntry() {
        val dir = Files.createTempDirectory("nf-restore-entry").toFile()
        val bad = File(dir, "bad.zip")
        ZipOutputStream(bad.outputStream()).use { out ->
            val manifest = "{\"schema\":\"nf-backup/1\",\"files\":[{\"path\":\"projects/a\",\"bytes\":300000000,\"sha256\":\"x\"}]}"
            out.putNextEntry(ZipEntry("manifest.json")); out.write(manifest.toByteArray()); out.closeEntry()
        }
        assertFalse(BackupRestoreService.inspect(bad).ok)
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
