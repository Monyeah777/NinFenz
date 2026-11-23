package dev.ninfenz.mobile.design

import dev.ninfenz.mobile.ui.design.CompositionSlot
import dev.ninfenz.mobile.ui.design.InformationRole
import dev.ninfenz.mobile.ui.design.ScreenAudit
import dev.ninfenz.mobile.ui.design.ScreenEvidence
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ScreenAuditTest {
    private fun good() = ScreenEvidence(
        typeSizes = setOf(22f, 16f, 12f),
        weights = setOf(600, 400),
        primaryActions = 1,
        accentAreaRatio = 0.1,
        spacing = listOf(4, 8, 12, 16, 24),
        minContrast = 7.0,
        stateHasText = true,
        stateHasShape = true,
        stateHasColor = true,
        scale200NoClip = true,
        composition = listOf(
            CompositionSlot(InformationRole.CONTEXT, "title"),
            CompositionSlot(InformationRole.PRIMARY, "body"),
            CompositionSlot(InformationRole.ACTION, "button")
        ),
        motionMs = setOf(150, 250),
        feedbackMs = 200
    )

    @Test
    fun aGoodScreenScoresFull() {
        val r = ScreenAudit.evaluate(good())
        assertEquals(12, r.passed)
        assertEquals(100, r.score)
        assertTrue(r.issues.isEmpty())
        assertFalse(r.blocked)
    }

    @Test
    fun missingEvidenceCannotPass() {
        val r = ScreenAudit.evaluate(
            good().copy(
                typeSizes = setOf(22f, 16f, 14f, 12f, 11f),
                weights = setOf(600, 500, 400),
                primaryActions = 2,
                accentAreaRatio = 0.3,
                spacing = listOf(6, 10),
                minContrast = 3.0,
                stateHasText = false,
                scale200NoClip = null,
                composition = emptyList(),
                motionMs = setOf(120),
                feedbackMs = 500
            )
        )
        assertTrue(r.score < 50)
        assertTrue(r.blocked)
        assertTrue(r.issues.any { it.id == "S-CLIP" })
    }
}
