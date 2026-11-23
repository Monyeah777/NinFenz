package dev.ninfenz.mobile.ui.design

/**
 * 感知层的可计算部分：把格式塔从“说法”变成阈值。
 * 纯数据/纯函数；不依赖 Compose，便于 JVM 单测。
 */
object Proximity {
    /** 组内 12 / 组间 24：组间至少是组内的 1.5 倍，否则会被读成同组。 */
    const val INTRA = Space.itemGap
    const val INTER = Space.section
    const val MIN_RATIO = 1.5

    fun ratio(): Double = INTER.toDouble() / INTRA
    fun isSeparated(): Boolean = ratio() >= MIN_RATIO
}

/** 视觉重量：面积 × 对比 × 色彩显著度 × 字重，作为“一屏一锚点”的预算。 */
data class Salience(
    val area: Double,
    val contrast: Double,
    val colorfulness: Double,
    val fontWeight: Int,
    val accent: Boolean
) {
    fun weight(): Double {
        require(area > 0 && contrast > 0 && colorfulness >= 0)
        val base = area * contrast * (1.0 + colorfulness)
        val weightFactor = fontWeight.coerceIn(100, 900) / 400.0
        return base * weightFactor * (if (accent) 1.4 else 1.0)
    }
}

object SalienceBudget {
    const val MAX_PRIMARY = 1
    const val MAX_ACCENT_AREA = 0.18
    fun accepts(primaryCount: Int, accentAreaRatio: Double): Boolean =
        primaryCount in 0..MAX_PRIMARY && accentAreaRatio in 0.0..MAX_ACCENT_AREA
}

/** 明度阶梯：深色/浅色都必须单调，且层级间有可感知差。 */
object GroundLadder {
    const val MIN_STEP = 0.01

    fun luminance(argb: Int): Double = Contrast.luminance(argb)

    fun steps(argb: List<Int>): List<Double> = argb.map { luminance(it) }

    fun isMonotonic(argb: List<Int>, dark: Boolean): Boolean {
        val s = steps(argb)
        return if (dark) s.zipWithNext().all { (a, b) -> b > a }
        else s.zipWithNext().all { (a, b) -> b < a }
    }

    fun hasPerceptibleStep(argb: List<Int>): Boolean =
        steps(argb).zipWithNext().all { (a, b) -> kotlin.math.abs(b - a) >= MIN_STEP }
}
