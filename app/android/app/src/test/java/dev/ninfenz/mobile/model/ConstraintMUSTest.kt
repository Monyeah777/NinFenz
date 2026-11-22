package dev.ninfenz.mobile.model

import dev.ninfenz.mobile.model.ConstraintMUS.Kind
import dev.ninfenz.mobile.model.ConstraintMUS.Rule
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ConstraintMUSTest {
    private fun r(id: String, kind: Kind, field: String = "f", value: String = "") = Rule(id, kind, field, value)

    @Test
    fun minMaxConflict() {
        val rules = listOf(r("min", Kind.MIN_CHARS, value = "100"), r("max", Kind.MAX_CHARS, value = "50"))
        assertFalse(ConstraintMUS.satisfiable(rules))
        assertEquals(listOf(rules), ConstraintMUS.minimalConflicts(rules))
    }

    @Test
    fun requiredForbiddenConflict() {
        val rules = listOf(r("r", Kind.REQUIRED), r("e", Kind.FORBIDDEN_EMPTY))
        assertEquals(listOf(rules), ConstraintMUS.minimalConflicts(rules))
    }

    @Test
    fun includeAvoidConflict() {
        val rules = listOf(r("i", Kind.MUST_INCLUDE, value = "A"), r("a", Kind.MUST_AVOID, value = "A"))
        assertEquals(listOf(rules), ConstraintMUS.minimalConflicts(rules))
    }

    @Test
    fun satisfiableSpec() {
        val rules = listOf(r("min", Kind.MIN_CHARS, value = "10"), r("max", Kind.MAX_CHARS, value = "20"))
        assertTrue(ConstraintMUS.satisfiable(rules))
        assertTrue(ConstraintMUS.minimalConflicts(rules).isEmpty())
    }

    @Test
    fun supersetNotReported() {
        val rules = listOf(r("min", Kind.MIN_CHARS, value = "100"), r("max", Kind.MAX_CHARS, value = "50"), r("r", Kind.REQUIRED))
        val mus = ConstraintMUS.minimalConflicts(rules)
        assertEquals(1, mus.size)
        assertEquals(2, mus[0].size)
    }

    @Test
    fun twoIndependentConflicts() {
        val rules = listOf(
            r("min", Kind.MIN_CHARS, field = "a", value = "100"),
            r("max", Kind.MAX_CHARS, field = "a", value = "50"),
            r("i", Kind.MUST_INCLUDE, field = "b", value = "X"),
            r("x", Kind.MUST_AVOID, field = "b", value = "X")
        )
        assertEquals(2, ConstraintMUS.minimalConflicts(rules).size)
    }

    @Test
    fun emptyIsSatisfiable() {
        assertTrue(ConstraintMUS.satisfiable(emptyList()))
        assertTrue(ConstraintMUS.minimalConflicts(emptyList()).isEmpty())
    }
}
