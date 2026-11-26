package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TextDiffTest {
    @Test
    fun identicalHasNoChanges() {
        val r = TextDiff.diff("a\nb\nc", "a\nb\nc")
        assertEquals(0, r.added)
        assertEquals(0, r.removed)
        assertFalse(r.degraded)
        assertTrue(r.lines.all { it.kind == DiffKind.EQUAL })
    }

    @Test
    fun addRemoveAndReplaceHaveLineNumbers() {
        val r = TextDiff.diff("a\nb\nc", "a\nB\nc\nd")
        assertEquals(2, r.added)
        assertEquals(1, r.removed)
        assertEquals(2, r.lines.first { it.kind == DiffKind.REMOVE }.oldLine)
        assertEquals(2, r.lines.first { it.kind == DiffKind.ADD }.newLine)
    }

    @Test
    fun largeInputDegradesExplicitly() {
        val oldText = (1..1200).joinToString("\n") { "line-" + it }
        val newText = (1..1200).joinToString("\n") { "changed-" + it }
        val r = TextDiff.diff(oldText, newText)
        assertTrue(r.degraded)
        assertEquals(1200, r.added)
        assertEquals(1200, r.removed)
    }
}
