package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PreservationVerifierTest {
    @Test
    fun verifiesExportedBundle() {
        val dir = Files.createTempDirectory("verify").toFile()
        val created = PreservationExporter.export("# 标题\n\n正文", "标题", "p1", dir)
        val result = PreservationVerifier.verify(created.file)
        assertTrue(result.errors.toString(), result.ok)
        assertTrue(result.title == "标题")
    }

    @Test
    fun rejectsTamperedDocument() {
        val dir = Files.createTempDirectory("verify-bad").toFile()
        val created = PreservationExporter.export("# 标题\n\n正文", "标题", "p1", dir)
        val bad = File(dir, "bad.preserve.zip")
        ZipFile(created.file).use { zip ->
            ZipOutputStream(bad.outputStream()).use { out ->
                zip.entries().asSequence().forEach { entry ->
                    out.putNextEntry(ZipEntry(entry.name).apply { time = 0L })
                    val bytes = zip.getInputStream(entry).readBytes()
                    out.write(if (entry.name == "document.md") "tamper".toByteArray() else bytes)
                    out.closeEntry()
                }
            }
        }
        assertFalse(PreservationVerifier.verify(bad).ok)
    }
}
