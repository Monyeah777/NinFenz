package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PackZipInstallerTest {
    private fun packZip(root: File, name: String = "demo", version: String = "1.0.0"): File {
        val zip = File(root, "pack.zip")
        ZipOutputStream(zip.outputStream()).use { out ->
            out.putNextEntry(ZipEntry("nf-pack.json"))
            out.write("{\"schema\":\"nf-pack/1\",\"id\":\"$name\",\"version\":\"$version\"}".toByteArray())
            out.closeEntry()
        }
        return zip
    }

    @Test
    fun installsNewPackFromZip() {
        val root = Files.createTempDirectory("nf-pack-zip").toFile()
        val result = PackZipInstaller.install(packZip(root), root)
        assertTrue(result.message, result.ok)
        assertEquals("demo", result.id)
        val target = File(root, "library/packs/demo/1.0.0")
        assertTrue(target.isDirectory)
        assertEquals("zip", PackRegistry.load(root)["demo@1.0.0"]?.source)
        assertFalse(File(root, "library/incoming").listFiles().orEmpty().any { it.isDirectory })
    }

    @Test
    fun duplicateZipIsRejected() {
        val root = Files.createTempDirectory("nf-pack-zip-dup").toFile()
        val zip = packZip(root)
        assertTrue(PackZipInstaller.install(zip, root).ok)
        val second = PackZipInstaller.install(zip, root)
        assertFalse(second.ok)
        assertTrue(second.message.contains("已存在"))
    }

    @Test
    fun missingManifestIsRejected() {
        val root = Files.createTempDirectory("nf-pack-zip-bad").toFile()
        val zip = File(root, "bad.zip")
        ZipOutputStream(zip.outputStream()).use { out ->
            out.putNextEntry(ZipEntry("readme.md"))
            out.write("no pack".toByteArray())
            out.closeEntry()
        }
        val result = PackZipInstaller.install(zip, root)
        assertFalse(result.ok)
        assertTrue(result.message.contains("nf-pack.json"))
    }
}
