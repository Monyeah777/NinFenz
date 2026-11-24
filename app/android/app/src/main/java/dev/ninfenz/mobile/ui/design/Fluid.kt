package dev.ninfenz.mobile.ui.design

/**
 * 流式缩放：只让间距/边距/容器随宽度插值；字号不随屏宽缩小。
 * 断点仍是阶跃，插值只用于断点内连续变化。
 */
data class FluidSpec(val min: Float, val max: Float, val fromWidth: Float = 0f, val toWidth: Float = 600f) {
    init {
        require(max >= min)
        require(toWidth > fromWidth)
    }

    fun value(width: Float): Float {
        val t = ((width - fromWidth) / (toWidth - fromWidth)).coerceIn(0f, 1f)
        return min + (max - min) * t
    }
}

object Fluid {
    val pagePadding = FluidSpec(16f, 32f)
    val sectionGap = FluidSpec(24f, 32f)
    val cardPadding = FluidSpec(12f, 16f)
    val maxContentWidth = FluidSpec(720f, 720f)

    /** 字号显式不流式：无障碍字号必须由系统 fontScale 控制。 */
    const val FLUID_TYPE = false
}
