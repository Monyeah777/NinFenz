package dev.ninfenz.mobile.ui.theme

import androidx.compose.ui.graphics.Color
import dev.ninfenz.mobile.ui.design.NfColor
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.pow

/** DoD 对比度：正文/大字按 WCAG 2.2 AA 阈值校验新主题。 */
class ContrastTest {

    private fun channel(c: Float): Double {
        val v = c.toDouble()
        return if (v <= 0.03928) v / 12.92 else ((v + 0.055) / 1.055).pow(2.4)
    }

    private fun luminance(color: Color): Double =
        0.2126 * channel(color.red) + 0.7152 * channel(color.green) + 0.0722 * channel(color.blue)

    private fun ratio(a: Color, b: Color): Double {
        val la = luminance(a)
        val lb = luminance(b)
        val hi = maxOf(la, lb)
        val lo = minOf(la, lb)
        return (hi + 0.05) / (lo + 0.05)
    }

    private fun assertBody(label: String, fg: Color, bg: Color) {
        val r = ratio(fg, bg)
        assertTrue(label + " contrast " + r + " < 4.5", r >= 4.5)
    }

    private fun assertLarge(label: String, fg: Color, bg: Color) {
        val r = ratio(fg, bg)
        assertTrue(label + " contrast " + r + " < 3.0", r >= 3.0)
    }

    @Test
    fun lightPaletteMeetsWcagAa() {
        val c = NfColor.light()
        assertBody("light onBackground", c.onBackground, c.background)
        assertBody("light onSurface", c.onSurface, c.surface)
        assertBody("light onPrimary", c.onPrimary, c.primary)
        assertBody("light onError", c.onError, c.error)
    }

    @Test
    fun darkPaletteMeetsWcagAa() {
        val c = NfColor.dark()
        assertBody("dark onBackground", c.onBackground, c.background)
        assertBody("dark onSurface", c.onSurface, c.surface)
        assertBody("dark onPrimary", c.onPrimary, c.primary)
        assertBody("dark onError", c.onError, c.error)
    }

    @Test
    fun primaryButtonLargeTextMeetsAaLarge() {
        assertLarge("light primary/bg", NfColor.light().primary, NfColor.light().background)
        assertLarge("dark primary/bg", NfColor.dark().primary, NfColor.dark().background)
    }
}
