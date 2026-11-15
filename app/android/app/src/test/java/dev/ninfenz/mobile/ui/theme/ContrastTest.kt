package dev.ninfenz.mobile.ui.theme

import androidx.compose.ui.graphics.Color
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.pow

/** DoD 对比度：正文/大字按 WCAG 2.2 AA 阈值校验品牌调色板。 */
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
        assertBody("light onBackground", NfPalette.LightOnBackground, NfPalette.LightBackground)
        assertBody("light onSurface", NfPalette.LightOnSurface, NfPalette.LightSurface)
        assertBody("light onPrimary", NfPalette.LightOnPrimary, NfPalette.LightPrimary)
        assertBody("light onError", NfPalette.LightOnError, NfPalette.LightError)
    }

    @Test
    fun darkPaletteMeetsWcagAa() {
        assertBody("dark onBackground", NfPalette.DarkOnBackground, NfPalette.DarkBackground)
        assertBody("dark onSurface", NfPalette.DarkOnSurface, NfPalette.DarkSurface)
        assertBody("dark onPrimary", NfPalette.DarkOnPrimary, NfPalette.DarkPrimary)
        assertBody("dark onError", NfPalette.DarkOnError, NfPalette.DarkError)
    }

    @Test
    fun primaryButtonLargeTextMeetsAaLarge() {
        assertLarge("light primary/bg", NfPalette.LightPrimary, NfPalette.LightBackground)
        assertLarge("dark primary/bg", NfPalette.DarkPrimary, NfPalette.DarkBackground)
    }
}
