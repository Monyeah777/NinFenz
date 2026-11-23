package dev.ninfenz.mobile.design

import dev.ninfenz.mobile.ui.design.Breakpoint
import dev.ninfenz.mobile.ui.design.Channel
import dev.ninfenz.mobile.ui.design.ChannelRanking
import dev.ninfenz.mobile.ui.design.ColorVision
import dev.ninfenz.mobile.ui.design.Composition
import dev.ninfenz.mobile.ui.design.CompositionSlot
import dev.ninfenz.mobile.ui.design.DataType
import dev.ninfenz.mobile.ui.design.Density
import dev.ninfenz.mobile.ui.design.Feedback
import dev.ninfenz.mobile.ui.design.GroundLadder
import dev.ninfenz.mobile.ui.design.InformationRole
import dev.ninfenz.mobile.ui.design.Palette
import dev.ninfenz.mobile.ui.design.Proximity
import dev.ninfenz.mobile.ui.design.Salience
import dev.ninfenz.mobile.ui.design.SalienceBudget
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DeepVisualSystemTest {
    @Test
    fun proximityHasMeasurableGroupBoundary() {
        assertTrue(Proximity.isSeparated())
        assertTrue(Proximity.ratio() >= 1.5)
    }

    @Test
    fun salienceBudgetAllowsOneAnchor() {
        val anchor = Salience(area = 1.0, contrast = 7.0, colorfulness = 0.2, fontWeight = 600, accent = true)
        val body = Salience(area = 1.0, contrast = 7.0, colorfulness = 0.0, fontWeight = 400, accent = false)
        assertTrue(anchor.weight() > body.weight())
        assertTrue(SalienceBudget.accepts(1, 0.1))
        assertFalse(SalienceBudget.accepts(2, 0.1))
        assertFalse(SalienceBudget.accepts(1, 0.2))
    }

    @Test
    fun groundLadderIsMonotonicAndPerceptible() {
        val dark = listOf(Palette.background.dark, Palette.surface.dark, Palette.surfaceRaised.dark, Palette.surfaceVariant.dark)
        assertTrue(GroundLadder.isMonotonic(dark, dark = true))
        assertTrue(GroundLadder.hasPerceptibleStep(dark))
    }

    @Test
    fun channelRankingMatchesDataType() {
        assertEquals(Channel.POSITION, ChannelRanking.forType(DataType.QUANTITATIVE).first())
        assertEquals(Channel.HUE, ChannelRanking.forType(DataType.NOMINAL).first { it == Channel.HUE })
        assertFalse(ChannelRanking.isEffective(DataType.QUANTITATIVE, Channel.HUE))
        assertTrue(ChannelRanking.isEffective(DataType.ORDINAL, Channel.VALUE))
    }

    @Test
    fun brandHueStaysInTheBrandSector() {
        val h = ColorVision.hue(Palette.primary.light)
        assertTrue("brand hue=$h", h in 158.0..178.0)
        val sim = ColorVision.simulate(Palette.error.light)
        assertTrue(ColorVision.deltaE76(Palette.error.light, sim) > 0.0)
    }

    @Test
    fun compositionHasOnePrimaryAndActionAtEnd() {
        val good = listOf(
            CompositionSlot(InformationRole.CONTEXT, "title"),
            CompositionSlot(InformationRole.PRIMARY, "body"),
            CompositionSlot(InformationRole.SUPPORTING, "meta"),
            CompositionSlot(InformationRole.ACTION, "button")
        )
        assertTrue(Composition.validate(good).isEmpty())
        val bad = listOf(
            CompositionSlot(InformationRole.ACTION, "button"),
            CompositionSlot(InformationRole.PRIMARY, "body")
        )
        assertTrue(Composition.validate(bad).isNotEmpty())
    }

    @Test
    fun responsiveDensityDoesNotShrinkLargeText() {
        assertEquals(1.0, Density.factor(320, 1.0f), 0.001)
        assertEquals(1.0, Density.factor(320, 1.3f), 0.001)
        assertEquals(0.9, Density.factor(500, 1.0f), 0.001)
        assertEquals(0.82, Density.factor(900, 1.0f), 0.001)
        assertEquals(Breakpoint.COMPACT, Breakpoint.forWidth(599))
        assertEquals(Breakpoint.MEDIUM, Breakpoint.forWidth(600))
        assertEquals(Breakpoint.EXPANDED, Breakpoint.forWidth(840))
    }

    @Test
    fun feedbackHasA400msBudget() {
        assertTrue(Feedback.isFast(150))
        assertFalse(Feedback.isFast(401))
        assertTrue(Feedback.SKELETON_AFTER_MS < Feedback.MAX_LATENCY_MS)
    }
}
