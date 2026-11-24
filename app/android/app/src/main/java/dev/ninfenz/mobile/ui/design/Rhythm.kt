package dev.ninfenz.mobile.ui.design

/** 垂直节奏：所有纵向间距落在 8dp 拍上；列表行高是拍的整数倍。 */
object Rhythm {
    const val BEAT = 8
    fun beat(n: Int): Int = n * BEAT
    fun isOnBeat(dp: Int): Boolean = dp % BEAT == 0
    val listRows = listOf(Sizes.listOneLine, Sizes.listTwoLine)
    fun sectionGap(index: Int): Int = beat(if (index == 0) 3 else 3)
    fun cardGap(): Int = beat(2)
}

/** 滚动体验：固定边界、锚点、回弹、恢复。 */
object ScrollPolicy {
    const val BOTTOM_NAV_HEIGHT = Sizes.navigationBar
    const val BOTTOM_CONTENT_GAP = Space.gutter
    const val TOP_APP_BAR = Sizes.topAppBar
    const val STICKY_SECTION_HEADER = true
    const val RESTORE_SCROLL_POSITION = true
    const val OVERSCROLL_ENABLED = false
    const val FLING_MIN_VELOCITY = 400

    fun contentBottomPadding(): Int = BOTTOM_NAV_HEIGHT + BOTTOM_CONTENT_GAP
    fun isStickyAnchor(enabled: Boolean): Boolean = enabled && STICKY_SECTION_HEADER
}
