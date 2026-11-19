package dev.ninfenz.mobile.data

import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.Assert.assertEquals
import org.junit.Test

class DocxTextImporterTest {
    @Test
    fun extractsParagraphs() {
        val file = File.createTempFile("nf-docx", ".docx")
        ZipOutputStream(file.outputStream()).use { out ->
            out.putNextEntry(ZipEntry("word/document.xml"))
            out.write(
                """<?xml version="1.0" encoding="UTF-8"?>
                <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                  <w:body>
                    <w:p><w:pPr><w:numPr/></w:pPr><w:r><w:t>Hello</w:t></w:r><w:r><w:t> DOCX</w:t></w:r></w:p>
                    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Second</w:t></w:r></w:p>
                    <w:tbl><w:tr><w:tc><w:p><w:r><w:t>A</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>B</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
                  </w:body>
                </w:document>""".trimIndent().toByteArray()
            )
            out.closeEntry()
        }
        val text = DocxTextImporter.extract(file)
        assertEquals("- Hello DOCX\n\n# Second\n\n| A | B |\n| --- | --- |", text)
        file.delete()
    }
}
