package dev.ninfenz.mobile.ui.design

/**
 * WCAG 相对亮度与对比度（纯函数，供演示屏与单测共用）。
 * 公式：https://www.w3.org/TR/WCAG22/#dfn-relative-luminance
 */
object Contrast {

    fun luminance(argb: Int): Double {
        fun channel(c: Int): Double {
            val s = c / 255.0
            return if (s <= 0.03928) s / 12.92 else Math.pow((s + 0.055) / 1.055, 2.4)
        }
        val r = (argb shr 16) and 0xFF
        val g = (argb shr 8) and 0xFF
        val b = argb and 0xFF
        return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
    }

    fun ratio(fg: Int, bg: Int): Double {
        val a = luminance(fg)
        val b = luminance(bg)
        val hi = maxOf(a, b)
        val lo = minOf(a, b)
        return (hi + 0.05) / (lo + 0.05)
    }

    fun ratio(token: ContrastPair, dark: Boolean): Double =
        ratio(if (dark) token.fg.dark else token.fg.light, if (dark) token.bg.dark else token.bg.light)
}
