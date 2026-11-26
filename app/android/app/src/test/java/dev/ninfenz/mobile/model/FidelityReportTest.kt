package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FidelityReportTest {
    @Test
    fun scoresFromStructureAndUnmapped() {
        val doc = ImportDoc(
            format = "docx",
            confidence = 55,
            candidates = emptyList(),
            source = ImportSource("file", "a.docx", null, 10, null),
            text = null,
            textPath = null,
            textDigest = null,
            structure = ImportStructure(
                headings = emptyList(),
                paragraphs = 2,
                codeBlocks = emptyList(),
                tables = listOf(ImportTableShape(2, 3))
            ),
            mappings = emptyList(),
            unmapped = listOf("x"),
            warnings = listOf(ImportWarning("NF-IMP-008", "图片未映射", null))
        )
        val report = FidelityReport.from(doc)
        assertEquals(4, report.headings + report.paragraphs + report.code + report.tables + report.unmapped)
        assertEquals(75, report.score)
        assertEquals("docx", report.sourceFormat)
        assertTrue(report.notes.any { it.contains("未映射") })
        assertTrue(report.lost.contains("图片未映射"))
    }
}
