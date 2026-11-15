package dev.ninfenz.mobile.ui

import org.junit.Assert.assertEquals
import org.junit.Test

/** PLAT-02 自适应分档：边界与三档映射（纯函数，JVM 单测）。 */
class AdaptiveLayoutTest {

    @Test
    fun compactBelow600() {
        assertEquals(LayoutClass.COMPACT, layoutClassFor(0))
        assertEquals(LayoutClass.COMPACT, layoutClassFor(360))
        assertEquals(LayoutClass.COMPACT, layoutClassFor(599))
    }

    @Test
    fun mediumBetween600And839() {
        assertEquals(LayoutClass.MEDIUM, layoutClassFor(600))
        assertEquals(LayoutClass.MEDIUM, layoutClassFor(720))
        assertEquals(LayoutClass.MEDIUM, layoutClassFor(839))
    }

    @Test
    fun expandedFrom840() {
        assertEquals(LayoutClass.EXPANDED, layoutClassFor(840))
        assertEquals(LayoutClass.EXPANDED, layoutClassFor(1280))
        assertEquals(LayoutClass.EXPANDED, layoutClassFor(2560))
    }

    @Test
    fun labelsAreNonEmptyAndUnique() {
        val labels = dev.ninfenz.mobile.state.Screen.entries.map { screenLabel(it) }
        assertEquals(labels.distinct().size, labels.size)
        assertEquals(true, labels.all { it.isNotBlank() })
    }
}
