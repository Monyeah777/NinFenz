package dev.ninfenz.mobile.design

import dev.ninfenz.mobile.ui.design.MotionPolicy
import dev.ninfenz.mobile.ui.design.ReadingMeasure
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TypographyPolicyTest {
    @Test
    fun readingMeasureStaysInTheReadableBand() {
        assertTrue(ReadingMeasure.latinOk(45))
        assertTrue(ReadingMeasure.latinOk(90))
        assertFalse(ReadingMeasure.latinOk(44))
        assertFalse(ReadingMeasure.latinOk(91))
        assertTrue(ReadingMeasure.cjkOk(20))
        assertTrue(ReadingMeasure.cjkOk(26))
        assertFalse(ReadingMeasure.cjkOk(27))
        assertEquals(20, ReadingMeasure.cjkFor(320, 16f))
        assertEquals(26, ReadingMeasure.cjkFor(720, 16f))
    }

    @Test
    fun reduceMotionZeroesDurationAndOnlyTokensAnimate() {
        assertEquals(0, MotionPolicy.durationMs(250, reduceMotion = true))
        assertEquals(250, MotionPolicy.durationMs(250, reduceMotion = false))
        assertTrue(MotionPolicy.isToken(150))
        assertFalse(MotionPolicy.isToken(120))
        assertFalse(MotionPolicy.shouldAnimate(120, reduceMotion = false))
        assertFalse(MotionPolicy.shouldAnimate(250, reduceMotion = true))
    }
}
