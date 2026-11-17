package dev.ninfenz.mobile.data

import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class DocxReferenceStylesTest {
    private fun zip(entries: Map<String, String>): File {
        val file = File.createTempFile("nf-ref", ".docx")
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
    fun readsStylesXml() {
        val styles = "<?xml version=\"1.0\"?><w:styles xmlns:w=\"x\"></w:styles>"
        assertEquals(styles, DocxReferenceStyles.extract(zip(mapOf("word/styles.xml" to styles))))
    }

    @Test
    fun readsSectPrFromDocumentXml() {
        val sect = "<w:sectPr><w:pgMar w:top=\"720\"/></w:sectPr>"
        val file = zip(mapOf("word/document.xml" to ("<w:document><w:body>" + sect + "</w:body></w:document>")))
        assertEquals(sect, DocxReferenceStyles.extractSectPr(file))
    }

    @Test
    fun readsThemeXml() {
        val theme = "<a:theme xmlns:a=\"x\"><a:name val=\"ref\"/></a:theme>"
        assertEquals(theme, DocxReferenceStyles.extractTheme(zip(mapOf("word/theme/theme1.xml" to theme))))
    }

    @Test
    fun readsNumberingXml() {
        val numbering = "<w:numbering xmlns:w=\"x\"></w:numbering>"
        assertEquals(numbering, DocxReferenceStyles.extractNumbering(zip(mapOf("word/numbering.xml" to numbering))))
    }

    @Test
    fun rejectsMissingOrNonStyles() {
        assertNull(DocxReferenceStyles.extract(zip(mapOf("word/document.xml" to "<w:document/>"))))
        assertNull(DocxReferenceStyles.extract(zip(mapOf("word/styles.xml" to "<not-styles/>"))))
    }
}
