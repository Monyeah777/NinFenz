package dev.ninfenz.mobile.data

import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class DocxStyleAuditTest {
    @get:Rule
    val tmp = TemporaryFolder()

    private fun docx(styles: String): File {
        val file = File(tmp.root, "a.docx")
        ZipOutputStream(file.outputStream()).use { zip ->
            zip.putNextEntry(ZipEntry("word/styles.xml"))
            zip.write(styles.toByteArray(Charsets.UTF_8))
            zip.closeEntry()
        }
        return file
    }

    @Test
    fun findsAppliedStyleIdsInExportedDocx() {
        val styles = "<w:styles><w:style w:styleId=\"Heading1\"/></w:styles>"
        val result = DocxStyleAudit.check(styles, docx(styles))
        assertEquals(1, result.checked)
        assertEquals(1, result.found)
        assertTrue(result.ok)
    }

    @Test
    fun reportsMissingStyleIds() {
        val applied = "<w:style w:styleId=\"Heading1\"/><w:style w:styleId=\"Quote\"/>"
        val result = DocxStyleAudit.check(applied, docx("<w:styles><w:style w:styleId=\"Heading1\"/></w:styles>"))
        assertEquals(2, result.checked)
        assertEquals(listOf("Quote"), result.missing)
        assertFalse(result.ok)
    }
}
