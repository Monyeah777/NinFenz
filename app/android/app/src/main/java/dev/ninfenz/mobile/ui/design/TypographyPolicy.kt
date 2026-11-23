package dev.ninfenz.mobile.ui.design

/** 行宽/动效策略：把排版惯例与减少动效变成可调用规则。 */
object ReadingMeasure {
    const val LATIN_MIN = 45
    const val LATIN_MAX = 90
    const val CJK_MIN = 20
    const val CJK_MAX = 26

    fun latinOk(chars: Int): Boolean = chars in LATIN_MIN..LATIN_MAX
    fun cjkOk(chars: Int): Boolean = chars in CJK_MIN..CJK_MAX
    fun cjkFor(widthDp: Int, sizeSp: Float): Int =
        (widthDp / sizeSp).toInt().coerceIn(CJK_MIN, CJK_MAX)
}

object MotionPolicy {
    /** 系统减少动效时直接归零；其余必须命中 150/250/300。 */
    fun durationMs(baseMs: Int, reduceMotion: Boolean): Int =
        if (reduceMotion) 0 else baseMs

    fun isToken(baseMs: Int): Boolean = baseMs in Motion.all

    fun shouldAnimate(baseMs: Int, reduceMotion: Boolean): Boolean =
        !reduceMotion && isToken(baseMs)
}
