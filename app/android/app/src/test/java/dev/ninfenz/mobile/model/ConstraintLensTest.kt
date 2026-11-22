package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ConstraintLensTest {
    private fun slot(id: String, required: Boolean = false, min: Int? = null, max: Int? = null, prefix: String? = null, suffix: String? = null, pattern: String? = null) =
        SpecSlot(id, id, "s", "text", required, minChars = min, maxChars = max, startsWith = prefix, endsWith = suffix, pattern = pattern)

    @Test
    fun validValueNoIssues() {
        val view = ConstraintLens.view(listOf(slot("A", required = true, min = 2, max = 5, prefix = "X")), mapOf("A" to "Xab"))
        assertTrue(view[0].issues.isEmpty())
    }

    @Test
    fun allIssuesReported() {
        val view = ConstraintLens.view(
            listOf(slot("A", required = true, min = 5, max = 2, prefix = "X", suffix = "Y", pattern = "[0-9]+")),
            mapOf("A" to "abc")
        )
        assertEquals(
            listOf(
                ConstraintLens.Issue.MIN,
                ConstraintLens.Issue.MAX,
                ConstraintLens.Issue.PREFIX,
                ConstraintLens.Issue.SUFFIX,
                ConstraintLens.Issue.PATTERN
            ),
            view[0].issues
        )
    }

    @Test
    fun blankRequired() {
        val view = ConstraintLens.view(listOf(slot("A", required = true)), emptyMap())
        assertEquals(listOf(ConstraintLens.Issue.REQUIRED), view[0].issues)
    }
}
