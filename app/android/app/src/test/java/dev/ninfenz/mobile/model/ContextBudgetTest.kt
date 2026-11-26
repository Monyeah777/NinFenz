package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ContextBudgetTest {
    @Test
    fun includesSectionsAndSourcesWithinBudget() {
        val pack = ContextBudget.pack(
            sections = listOf("S1" to "开场", "S2" to "推进"),
            sources = listOf("source excerpt"),
            budgetTokens = 1000
        )
        assertEquals(3, pack.chunks.size)
        assertEquals(false, pack.trimmed)
        assertTrue(pack.usedTokens > 0)
    }

    @Test
    fun trimsWhenOverBudgetAndMarksIt() {
        val long = "x".repeat(400)
        val pack = ContextBudget.pack(listOf("S1" to long, "S2" to long), budgetTokens = 10)
        assertTrue(pack.trimmed)
        assertTrue(pack.usedTokens <= 10)
        assertTrue(pack.chunks.any { it.truncated })
        assertTrue(pack.notes.any { it.contains("截断") })
    }

    @Test
    fun zeroBudgetYieldsEmptyPack() {
        val pack = ContextBudget.pack(listOf("S1" to "abc"), budgetTokens = 0)
        assertTrue(pack.chunks.isEmpty())
        assertEquals(0, pack.usedTokens)
        assertTrue(pack.notes.isNotEmpty())
    }
}
