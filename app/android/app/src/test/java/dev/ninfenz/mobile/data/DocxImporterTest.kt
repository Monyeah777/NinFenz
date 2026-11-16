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
    fun extractsListParagraphs() {
        val xml = "<w:document><w:body><w:p><w:pPr><w:numPr/></w:pPr><w:r><w:t>项</w:t></w:r></w:p></w:body></w:document>"
        assertTrue(DocxImporter.extract(docx(xml)).contains("- 项"))
    }

    @Test
    fun extractsTables() {
        val xml = "<w:document><w:body><w:tbl>" +
            "<w:tr><w:tc><w:p><w:r><w:t>A</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>B</w:t></w:r></w:p></w:tc></w:tr>" +
            "<w:tr><w:tc><w:p><w:r><w:t>1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>2</w:t></w:r></w:p></w:tc></w:tr>" +
            "</w:tbl></w:body></w:document>"
        val md = DocxImporter.extract(docx(xml))
        assertTrue(md.contains("| A | B |"))
        assertTrue(md.contains("| 1 | 2 |"))
    }

    @Test
    fun extractsBoldAndItalicRuns() {
        val xml = "<w:document><w:body><w:p>" +
            "<w:r><w:rPr><w:b/></w:rPr><w:t>粗</w:t></w:r>" +
            "<w:r><w:rPr><w:i/></w:rPr><w:t>斜</w:t></w:r>" +
            "</w:p></w:body></w:document>"
        val md = DocxImporter.extract(docx(xml))
        assertTrue(md.contains("**粗**"))
        assertTrue(md.contains("*斜*"))
    }

    @Test
    fun extractsHyperlinks() {
        val f = File.createTempFile("nf-docx-link", ".docx")
        ZipOutputStream(f.outputStream()).use { out ->
            out.putNextEntry(ZipEntry("word/document.xml"))
            out.write(("<w:document><w:body><w:p><w:hyperlink r:id=\"rId1\">" +
                "<w:r><w:t>官网</w:t></w:r></w:hyperlink></w:p></w:body></w:document>").toByteArray())
            out.closeEntry()
            out.putNextEntry(ZipEntry("word/_rels/document.xml.rels"))
            out.write(("<Relationships><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink\" Target=\"https://example.com\"/></Relationships>").toByteArray())
            out.closeEntry()
        }
        assertTrue(DocxImporter.extract(f).contains("[官网](https://example.com)"))
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
