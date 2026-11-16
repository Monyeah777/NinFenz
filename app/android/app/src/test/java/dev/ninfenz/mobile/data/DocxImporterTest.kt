package dev.ninfenz.mobile.data

import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.Assert.assertTrue
import org.junit.Test

class DocxImporterTest {
    private fun docx(body: String): File {
        val f = File.createTempFile("nf-docx", ".docx")
        ZipOutputStream(f.outputStream()).use { out ->
            out.putNextEntry(ZipEntry("word/document.xml"))
            out.write(body.toByteArray())
            out.closeEntry()
        }
        return f
    }

    @Test
    fun extractsParagraphsAndHeadings() {
        val xml = "<w:document><w:body>" +
            "<w:p><w:pPr><w:pStyle w:val=\"Heading1\"/></w:pPr><w:r><w:t>标题</w:t></w:r></w:p>" +
            "<w:p><w:r><w:t>正文</w:t></w:r></w:p>" +
            "</w:body></w:document>"
        val f = docx(xml)
        assertTrue(DocxImporter.detect(f))
        val md = DocxImporter.extract(f)
        assertTrue(md.contains("# 标题"))
        assertTrue(md.contains("正文"))
    }

    @Test
    fun rejectsMissingDocument() {
        val f = File.createTempFile("nf-docx-bad", ".docx")
        ZipOutputStream(f.outputStream()).use { out ->
            out.putNextEntry(ZipEntry("x")); out.write(byteArrayOf(1)); out.closeEntry()
        }
        assertTrue(runCatching { DocxImporter.extract(f) }.isFailure)
    }
}
