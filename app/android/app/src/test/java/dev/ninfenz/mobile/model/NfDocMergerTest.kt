package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class NfDocMergerTest {
    @Test
    fun keepsBothSidesAndReportsSectionConflict() {
        val left = NfDocModel.fromMarkdown("A", "p1", "# 开篇\n\n甲")
        val right = NfDocModel.fromMarkdown("B", "p2", "# 开篇\n\n乙")
        val result = NfDocMerger.merge(left, right, "合并")
        assertEquals(listOf("p1", "p2"), result.doc.sources)
        assertTrue(result.conflicts.any { it.title == "开篇" })
        assertTrue(result.doc.blocks.any { it.text.contains("甲") })
        assertTrue(result.doc.blocks.any { it.text.contains("乙") })
    }

    @Test
    fun deduplicatesIdenticalBlocks() {
        val a = NfDocModel.fromMarkdown("A", "p1", "同一段")
        val b = NfDocModel.fromMarkdown("B", "p2", "同一段")
        val result = NfDocMerger.merge(a, b, "合并")
        assertEquals(1, result.doc.blocks.count { it.text == "同一段" })
    }
}
