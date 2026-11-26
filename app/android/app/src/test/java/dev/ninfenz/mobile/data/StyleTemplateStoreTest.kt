package dev.ninfenz.mobile.data

import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class StyleTemplateStoreTest {
    @get:Rule
    val tmp = TemporaryFolder()

    @Test
    fun savesListsDeletesAndExtractsDocxStyles() {
        val store = StyleTemplateStore(tmp.root)
        val first = store.save("A", "docx", "<w:styles/>", "<w:sectPr/>")
        assertEquals(1, store.list().size)
        assertEquals("<w:styles/>", store.list().first().stylesXml)
        store.delete(first.id)
        assertTrue(store.list().isEmpty())

        val docx = File(tmp.root, "a.docx")
        ZipOutputStream(docx.outputStream()).use { out ->
            out.putNextEntry(ZipEntry("word/styles.xml"))
            out.write("<w:styles>demo</w:styles>".toByteArray())
            out.closeEntry()
        }
        val extracted = store.fromDocx(docx, "Docx")
        assertTrue(extracted.stylesXml.contains("demo"))
        assertEquals("docx", extracted.sourceFormat)
        assertEquals(1, store.list().size)
    }
}
