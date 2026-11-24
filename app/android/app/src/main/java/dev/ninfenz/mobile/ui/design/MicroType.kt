package dev.ninfenz.mobile.ui.design

/**
 * 微观排版硬约束：行宽、行高、字距、断行、标点、数字。
 * 不是“建议”，不满足即失败。
 */
object MicroType {
    const val CJK_MIN_CHARS = 20
    const val CJK_MAX_CHARS = 26
    const val LATIN_MIN_CHARS = 45
    const val LATIN_MAX_CHARS = 90
    const val LINE_HEIGHT_MIN = 1.5
    const val LINE_HEIGHT_MAX = 1.75
    const val HASH_GROUP = 4
    const val TRACKING_SP = 0f

    fun lineHeightRatio(size: Float, line: Float): Double = line.toDouble() / size.toDouble()

    fun validLineHeight(size: Float, line: Float): Boolean =
        lineHeightRatio(size, line) in LINE_HEIGHT_MIN..LINE_HEIGHT_MAX

    fun validTracking(tracking: Float): Boolean = tracking == TRACKING_SP

    /** 孤行：正文最后一行只剩 1 个汉字/词，且正文超过 3 行。 */
    fun isWidow(lastLineChars: Int, totalLines: Int): Boolean =
        totalLines > 3 && lastLineChars == 1

    /** 哈希每 4 字符分组，便于人工核对；不改变原始字符。 */
    fun groupHash(raw: String, group: Int = HASH_GROUP): String =
        raw.chunked(group).joinToString(" ")

    /** 中文引号成对；不把直引号留在正文。 */
    fun quote(text: String): String = "“" + text.trim('"') + "”"

    fun cjkLineChars(widthDp: Int, sizeSp: Float): Int =
        (widthDp / sizeSp).toInt().coerceIn(CJK_MIN_CHARS, CJK_MAX_CHARS)
}
