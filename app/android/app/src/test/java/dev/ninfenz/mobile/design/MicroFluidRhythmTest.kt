package dev.ninfenz.mobile.design

import dev.ninfenz.mobile.ui.design.Announcement
import dev.ninfenz.mobile.ui.design.Fluid
import dev.ninfenz.mobile.ui.design.Haptics
import dev.ninfenz.mobile.ui.design.InsetsPolicy
import dev.ninfenz.mobile.ui.design.MicroType
import dev.ninfenz.mobile.ui.design.Rhythm
import dev.ninfenz.mobile.ui.design.ScrollPolicy
import dev.ninfenz.mobile.ui.design.Sizes
import dev.ninfenz.mobile.ui.design.TypeScale
import dev.ninfenz.mobile.ui.design.UiState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MicroFluidRhythmTest {
    @Test
    fun microTypeHasHardBounds() {
        assertTrue(MicroType.validLineHeight(TypeScale.body.size, TypeScale.body.line))
        assertTrue(MicroType.validLineHeight(TypeScale.bodyLong.size, TypeScale.bodyLong.line))
        assertTrue(MicroType.validLineHeight(TypeScale.meta.size, TypeScale.meta.line))
        assertTrue(MicroType.validTracking(TypeScale.body.tracking))
        assertTrue(MicroType.isWidow(1, 4))
        assertFalse(MicroType.isWidow(2, 4))
        assertEquals("88d2 6e9a 4f1c", MicroType.groupHash("88d26e9a4f1c"))
        assertEquals("“正文”", MicroType.quote("正文"))
        assertEquals(20, MicroType.cjkLineChars(320, 16f))
        assertEquals(26, MicroType.cjkLineChars(720, 16f))
    }

    @Test
    fun fluidOnlyMovesSpacingAndClamps() {
        assertEquals(16f, Fluid.pagePadding.value(0f), 0.001f)
        assertEquals(24f, Fluid.pagePadding.value(300f), 0.001f)
        assertEquals(32f, Fluid.pagePadding.value(900f), 0.001f)
        assertEquals(16f, Fluid.pagePadding.value(-100f), 0.001f)
        assertFalse(Fluid.FLUID_TYPE)
    }

    @Test
    fun rhythmAndScrollStayOnBeat() {
        assertTrue(Rhythm.listRows.all { it % Rhythm.BEAT == 0 })
        assertTrue(Rhythm.isOnBeat(Rhythm.sectionGap(1)))
        assertEquals(96, ScrollPolicy.contentBottomPadding())
        assertEquals(Sizes.navigationBar, ScrollPolicy.BOTTOM_NAV_HEIGHT)
        assertFalse(ScrollPolicy.OVERSCROLL_ENABLED)
        assertTrue(InsetsPolicy.IME_BOTTOM_PADDING)
    }

    @Test
    fun nonVisualStatesAreDeterministic() {
        assertEquals(160, Haptics.forState(UiState.ERROR).amplitude)
        assertEquals(80, Haptics.forState(UiState.SIGNED).amplitude)
        assertEquals(0, Haptics.forState(UiState.LOADING).amplitude)
        assertNotNull(Announcement.forState(UiState.ERROR))
        assertNull(Announcement.forState(UiState.LOADING))
    }
}
