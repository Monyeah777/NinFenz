package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class HtmlValidatorTest {
    @Test
    fun acceptsExporterOutput() {
        val dir = Files.createTempDirectory("nf-html-valid").toFile()
        val created = HtmlExporter.export("# x", "t", dir)
        assertTrue(HtmlValidator.inspect(created.file).ok)
    }

    @Test
    fun rejectsBrokenHtml() {
        val dir = Files.createTempDirectory("nf-html-bad").toFile()
        val f = File(dir, "bad.html").apply { writeText("<p>no</p>") }
        assertFalse(HtmlValidator.inspect(f).ok)
        assertFalse(HtmlValidator.inspect(File(dir, "missing.html")).ok)
    }
}
