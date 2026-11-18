package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class TemplateCandidateTest {
    @Test
    fun buildsRequiredSpecFieldsFromSlices() {
        val md = "# 标题\n\n正文\n\n# 第二章\n\n另一段"
        val spec = TemplateCandidate.fromSlices("source", MarkdownSlicer.slice(MarkdownBlocks.parse(md)))
        assertNotNull(spec)
        assertEquals("nf-md-spec/1", spec!!["schema"].toString().trim('"'))
        assertEquals("标题", spec["title"].toString().trim('"'))
        assertEquals(2, spec["sections"].toString().split("SEC-").size - 1)
        assertEquals(2, spec["slots"].toString().split("SLT-").size - 1)
    }
}
