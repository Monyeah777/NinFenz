package dev.ninfenz.mobile.data

import java.nio.file.Files
import java.util.zip.ZipFile
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DiagnosticsBundleTest {
    @Test
    fun bundleContainsDiagnosticsAndReadmeOnly() {
        val dir = Files.createTempDirectory("nf-diag").toFile()
        val created = DiagnosticsBundle.create(dir, "app=test\\ncore=ok\\n")
        ZipFile(created.file).use { zip ->
            val names = zip.entries().toList().map { it.name }.sorted()
            assertEquals(listOf("README.txt", "diagnostics.txt"), names)
            val text = zip.getInputStream(zip.getEntry("diagnostics.txt")).bufferedReader().readText()
            assertTrue(text.contains("core=ok"))
            assertTrue(zip.getInputStream(zip.getEntry("README.txt")).bufferedReader().readText().contains("无网络"))
        }
    }

    @Test
    fun createsDistinctFiles() {
        val dir = Files.createTempDirectory("nf-diag-2").toFile()
        val a = DiagnosticsBundle.create(dir, "a")
        Thread.sleep(2)
        val b = DiagnosticsBundle.create(dir, "b")
        assertTrue(a.file.absolutePath != b.file.absolutePath)
    }
}
