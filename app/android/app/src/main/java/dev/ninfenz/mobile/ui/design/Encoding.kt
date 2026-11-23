package dev.ninfenz.mobile.ui.design

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

/** Bertin 编码选择：先按数据类型选通道，再谈样式。 */
enum class DataType { QUANTITATIVE, ORDINAL, NOMINAL }

enum class Channel { POSITION, SIZE, VALUE, HUE, SHAPE, ORIENTATION, TEXTURE }

object ChannelRanking {
    /**
     * 定量：位置 > 长度/大小 > 明度 > 纹理；色相不适合表达大小。
     * 定序：位置 > 明度 > 大小 > 纹理；颜色只做分类。
     * 定类：位置/形状/色相/纹理；不用大小表达类别。
     */
    fun forType(type: DataType): List<Channel> = when (type) {
        DataType.QUANTITATIVE -> listOf(
            Channel.POSITION, Channel.SIZE, Channel.VALUE, Channel.ORIENTATION, Channel.TEXTURE
        )
        DataType.ORDINAL -> listOf(
            Channel.POSITION, Channel.VALUE, Channel.SIZE, Channel.ORIENTATION, Channel.TEXTURE
        )
        DataType.NOMINAL -> listOf(
            Channel.POSITION, Channel.SHAPE, Channel.HUE, Channel.TEXTURE, Channel.ORIENTATION
        )
    }

    fun isEffective(type: DataType, channel: Channel): Boolean = channel in forType(type)
}

/** 色觉模拟与色差：状态不能只靠红/绿。 */
object ColorVision {
    // Machado et al. 2009 近似矩阵（0–1 线性空间）。
    private val deutan = arrayOf(
        doubleArrayOf(0.625, 0.375, 0.0),
        doubleArrayOf(0.700, 0.300, 0.0),
        doubleArrayOf(0.000, 0.300, 0.700)
    )
    private val protan = arrayOf(
        doubleArrayOf(0.567, 0.433, 0.0),
        doubleArrayOf(0.558, 0.442, 0.0),
        doubleArrayOf(0.000, 0.242, 0.758)
    )

    private fun linear(c: Int): Double {
        val s = c / 255.0
        return if (s <= 0.04045) s / 12.92 else Math.pow((s + 0.055) / 1.055, 2.4)
    }

    private fun gamma(c: Double): Int = (255 * if (c <= 0.0031308) c * 12.92 else 1.055 * Math.pow(c, 1 / 2.4) - 0.055).toInt().coerceIn(0, 255)

    fun simulate(argb: Int, deuteranopia: Boolean = true): Int {
        val m = if (deuteranopia) deutan else protan
        val r = linear((argb shr 16) and 0xFF)
        val g = linear((argb shr 8) and 0xFF)
        val b = linear(argb and 0xFF)
        val nr = m[0][0] * r + m[0][1] * g + m[0][2] * b
        val ng = m[1][0] * r + m[1][1] * g + m[1][2] * b
        val nb = m[2][0] * r + m[2][1] * g + m[2][2] * b
        return (0xFF shl 24) or (gamma(nr) shl 16) or (gamma(ng) shl 8) or gamma(nb)
    }

    fun deltaE76(a: Int, b: Int): Double {
        val dr = ((a shr 16) and 0xFF) - ((b shr 16) and 0xFF)
        val dg = ((a shr 8) and 0xFF) - ((b shr 8) and 0xFF)
        val db = (a and 0xFF) - (b and 0xFF)
        return kotlin.math.sqrt((dr * dr + dg * dg + db * db).toDouble())
    }

    fun statusSeparated(): Boolean {
        val colors = listOf(
            Palette.error.light, Palette.warning.light, Palette.success.light, Palette.info.light
        )
        return colors.indices.all { i ->
            colors.indices.all { j ->
                i >= j || (deltaE76(colors[i], colors[j]) >= 24 || deltaE76(simulate(colors[i]), simulate(colors[j])) >= 24)
            }
        }
    }

    /** HSL 色相，0–360。 */
    fun hue(argb: Int): Double {
        val r = ((argb shr 16) and 0xFF) / 255.0
        val g = ((argb shr 8) and 0xFF) / 255.0
        val b = (argb and 0xFF) / 255.0
        val mx = max(r, max(g, b)); val mn = min(r, min(g, b)); val d = mx - mn
        if (abs(d) < 1e-9) return 0.0
        var h = when (mx) {
            r -> ((g - b) / d) % 6
            g -> (b - r) / d + 2
            else -> (r - g) / d + 4
        } * 60
        if (h < 0) h += 360
        return h
    }
}
