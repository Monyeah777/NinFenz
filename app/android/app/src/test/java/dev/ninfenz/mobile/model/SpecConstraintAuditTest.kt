package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SpecConstraintAuditTest {
    private fun slot(id: String, required: Boolean = false, min: Int? = null, max: Int? = null) =
        SpecSlot(id, id, "s", "text", required, minChars = min, maxChars = max)

    @Test
    fun minGreaterThanMax() {
        val conflicts = SpecConstraintAudit.conflicts(listOf(slot("A", min = 100, max = 50)))
        assertEquals(1, conflicts.size)
        assertEquals(2, conflicts[0].size)
    }

    @Test
    fun requiredZeroMax() {
        val conflicts = SpecConstraintAudit.conflicts(listOf(slot("A", required = true, max = 0)))
        assertEquals(1, conflicts.size)
    }

    @Test
    fun validSpecNoConflict() {
        assertTrue(SpecConstraintAudit.conflicts(listOf(slot("A", required = true, min = 1, max = 10))).isEmpty())
    }
}
