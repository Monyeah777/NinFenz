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

class DocxHeadingAuditTest {
    @get:Rule
    val tmp = TemporaryFolder()

    private fun docx(document: String): File {
        val file = File(tmp.root, "a.docx")
        ZipOutputStream(file.outputStream()).use { zip ->
            zip.putNextEntry(ZipEntry("word/document.xml"))
            zip.write(document.toByteArray(Charsets.UTF_8))
            zip.closeEntry()
        }
        return file
    }

    @Test
    fun comparesMarkdownAndStyledHeadings() {
        val document = "<w:document><w:p><w:pPr><w:pStyle w:val=\"Heading1\"/></w:pPr></w:p></w:document>"
        val ok = DocxHeadingAudit.check("# A\n\n## B", docx(document + document))
        assertEquals(2, ok.markdownHeadings)
        assertEquals(2, ok.styledHeadings)
        assertTrue(ok.ok)
        val bad = DocxHeadingAudit.check("# A\n\n## B\n\n### C", docx(document))
        assertFalse(bad.ok)
    }
}
