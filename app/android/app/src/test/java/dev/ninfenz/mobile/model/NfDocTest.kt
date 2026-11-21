package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class NfDocTest {
    @Test
    fun markdownBecomesStructuredDoc() {
        val doc = NfDocModel.fromMarkdown("活动稿", "p1", "# 开篇\n\n正文\n\n|a|b|\n|-|-|\n|1|2|")
        assertEquals("活动稿", doc.title)
        assertEquals(listOf("p1"), doc.sources)
        assertTrue(doc.blocks.any { it.type == "section" })
        assertTrue(doc.blocks.any { it.type == "table" })
        assertTrue(doc.blocks.all { it.source == "p1" })
    }

    @Test
    fun appendKeepsSourcesAndReindexes() {
        val a = NfDocModel.fromMarkdown("A", "p1", "A")
        val b = NfDocModel.fromMarkdown("B", "p2", "B")
        val merged = NfDocModel.append(listOf(a, b), "合并")
        assertEquals(listOf("p1", "p2"), merged.sources)
        assertEquals(listOf("b1", "b2"), merged.blocks.map { it.id })
    }

    @Test
    fun jsonRoundTrip() {
        val doc = NfDocModel.fromMarkdown("标题", "src", "# 节\n\n正文")
        val parsed = NfDocModel.parse(NfDocModel.toJson(doc))
        assertEquals(doc.title, parsed.title)
        assertEquals(doc.blocks.size, parsed.blocks.size)
        assertEquals("section", parsed.blocks.first().type)
    }
}
