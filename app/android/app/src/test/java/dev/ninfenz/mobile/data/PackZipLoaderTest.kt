package dev.ninfenz.mobile.data

import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PackZipLoaderTest {

    private fun zip(vararg entries: Pair<String, String>): File {
        val file = File.createTempFile("nf-pack", ".zip")
        ZipOutputStream(FileOutputStream(file)).use { out ->
            for ((name, content) in entries) {
                out.putNextEntry(ZipEntry(name))
                out.write(content.toByteArray())
                out.closeEntry()
            }
        }
        return file
    }

    @Test
    fun extractsRootManifest() {
        val zip = zip("nf-pack.json" to "{\"id\":\"p\"}", "protocol/a.json" to "{}")
        val dest = File.createTempFile("nf-pack-out", "").let { it.delete(); it }
        val root = PackZipLoader.extract(zip, dest)
        assertEquals(dest.canonicalPath, root.canonicalPath)
        assertTrue(File(root, "protocol/a.json").isFile)
    }

    @Test
    fun extractsSingleTopLevelDirectory() {
        val zip = zip("pack/nf-pack.json" to "{\"id\":\"p\"}", "pack/spec/a.json" to "{}")
        val dest = File.createTempFile("nf-pack-out2", "").let { it.delete(); it }
        val root = PackZipLoader.extract(zip, dest)
        assertTrue(root.canonicalPath.endsWith("pack"))
        assertTrue(File(root, "spec/a.json").isFile)
    }

    @Test
    fun rejectsZipSlip() {
        val zip = zip("../evil.txt" to "x")
        val dest = File.createTempFile("nf-pack-out3", "").let { it.delete(); it }
        val failed = runCatching { PackZipLoader.extract(zip, dest) }.isFailure
        assertTrue(failed)
    }

    @Test
    fun rejectsControlCharacterEntryName() {
        val zip = zip("nf-\u0001.json" to "{}")
        val dest = File.createTempFile("nf-pack-out6", "").let { it.delete(); it }
        assertTrue(runCatching { PackZipLoader.extract(zip, dest) }.isFailure)
    }

    @Test
    fun rejectsCompressionBomb() {
        val file = File.createTempFile("nf-pack-bomb", ".zip")
        ZipOutputStream(FileOutputStream(file)).use { out ->
            out.putNextEntry(ZipEntry("nf-pack.json")); out.write("{}".toByteArray()); out.closeEntry()
            out.putNextEntry(ZipEntry("zeros.bin"))
            val chunk = ByteArray(1024 * 1024)
            repeat(20) { out.write(chunk) }
            out.closeEntry()
        }
        val dest = File.createTempFile("nf-pack-out7", "").let { it.delete(); it }
        assertTrue(runCatching { PackZipLoader.extract(file, dest) }.isFailure)
    }

    @Test
    fun rejectsMissingManifest() {
        val zip = zip("readme.txt" to "x")
        val dest = File.createTempFile("nf-pack-out4", "").let { it.delete(); it }
        val failed = runCatching { PackZipLoader.extract(zip, dest) }.isFailure
        assertTrue(failed)
    }
}
