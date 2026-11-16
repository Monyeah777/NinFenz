package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import java.util.zip.CRC32
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class EpubValidatorTest {
    @Test
    fun acceptsExporterOutput() {
        val dir = Files.createTempDirectory("nf-epub-valid").toFile()
        val created = EpubExporter.export("# 章\n\n正文", "标题", dir)
        val result = EpubValidator.inspect(created.file)
        assertTrue(result.issues.toString(), result.ok)
    }

    @Test
    fun rejectsZipWithoutEpubStructure() {
        val dir = Files.createTempDirectory("nf-epub-bad").toFile()
        val file = File(dir, "bad.epub")
        ZipOutputStream(file.outputStream()).use { out ->
            out.putNextEntry(ZipEntry("hello.txt")); out.write("x".toByteArray()); out.closeEntry()
        }
        val result = EpubValidator.inspect(file)
        assertFalse(result.ok)
        assertTrue(result.issues.any { it.contains("mimetype") || it.contains("container") })
    }

    @Test
    fun rejectsMissingFile() {
        val dir = Files.createTempDirectory("nf-epub-missing").toFile()
        assertFalse(EpubValidator.inspect(File(dir, "no.epub")).ok)
    }
}
