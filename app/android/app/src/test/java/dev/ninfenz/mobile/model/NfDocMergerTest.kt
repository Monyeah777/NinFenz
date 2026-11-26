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
    fun resolvesConflictByKeepingOneSide() {
        val left = NfDocModel.fromMarkdown("A", "p1", "# 开篇\n\n甲")
        val right = NfDocModel.fromMarkdown("B", "p2", "# 开篇\n\n乙")
        val merged = NfDocMerger.merge(left, right, "合并")
        val conflict = merged.conflicts.first { it.title == "开篇" }
        val resolved = NfDocMerger.resolve(merged.doc, conflict, NfDocMerger.Keep.LEFT)
        assertTrue(resolved.blocks.any { it.text.contains("甲") })
        assertTrue(resolved.blocks.joinToString(" | ") { it.type + ":" + it.text + ":" + it.source }, resolved.blocks.none { it.text.contains("乙") })
    }

    @Test
    fun threeWayTakesIndependentChangesAndFlagsSameBlock() {
        val base = NfDocModel.fromMarkdown("base", "base", "# 开篇\n\n甲\n\n乙")
        val left = NfDocModel.fromMarkdown("left", "left", "# 开篇\n\n甲改\n\n乙")
        val right = NfDocModel.fromMarkdown("right", "right", "# 开篇\n\n甲\n\n乙改")
        val merged = NfDocMerger.merge3(base, left, right, "合并")
        assertTrue(merged.doc.blocks.any { it.text.contains("甲改") })
        assertTrue(merged.doc.blocks.any { it.text.contains("乙改") })
        assertTrue(merged.conflicts.isEmpty())

        val both = NfDocModel.fromMarkdown("both", "both", "# 开篇\n\n甲再改\n\n乙")
        val conflict = NfDocMerger.merge3(base, left, both, "合并")
        assertTrue(conflict.conflicts.any { it.reason == "同块双改" })
    }

    @Test
    fun deduplicatesIdenticalBlocks() {
        val a = NfDocModel.fromMarkdown("A", "p1", "同一段")
        val b = NfDocModel.fromMarkdown("B", "p2", "同一段")
        val result = NfDocMerger.merge(a, b, "合并")
        assertEquals(1, result.doc.blocks.count { it.text == "同一段" })
    }
}
