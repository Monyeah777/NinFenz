package dev.ninfenz.mobile.ui.design

/** Kress & van Leeuwen 的信息价值：位置不是装饰，是语义。 */
enum class InformationRole { CONTEXT, PRIMARY, SUPPORTING, ACTION }

data class CompositionSlot(val role: InformationRole, val label: String)

object Composition {
    /** 一屏只能有一个 PRIMARY、一个 ACTION；CONTEXT 必须 first，ACTION 必须 last。 */
    fun validate(slots: List<CompositionSlot>): List<String> {
        val errors = mutableListOf<String>()
        if (slots.count { it.role == InformationRole.PRIMARY } != 1) errors += "primary must be exactly 1"
        if (slots.count { it.role == InformationRole.ACTION } > 1) errors += "action must be <= 1"
        if (slots.firstOrNull()?.role != InformationRole.CONTEXT) errors += "context must be first"
        if (slots.lastOrNull()?.role != InformationRole.ACTION) errors += "action must be last"
        return errors
    }
}

/** Lupton 网格：4/8/12 列随断点，内容限宽 720。 */
enum class Breakpoint(val minWidth: Int, val columns: Int) {
    COMPACT(0, 4),
    MEDIUM(Layout.breakpointMedium, 8),
    EXPANDED(Layout.breakpointExpanded, 12),
    LARGE(Layout.breakpointLarge, 12);

    companion object {
        fun forWidth(width: Int): Breakpoint = entries.last { width >= it.minWidth }
    }
}

object Density {
    /**
     * 紧凑度不是写死 0.75：窄屏/大字要回到 1.0，避免压缩后反而难读。
     */
    fun factor(widthDp: Int, fontScale: Float): Double {
        if (fontScale >= 1.3f) return 1.0
        val widthFactor = when {
            widthDp < 360 -> 1.0
            widthDp < 600 -> 0.9
            else -> 0.82
        }
        return widthFactor.coerceIn(0.75, 1.0)
    }
}

/** Doherty 阈值：反馈 <400ms；长任务先给骨架。 */
object Feedback {
    const val MAX_LATENCY_MS = 400
    const val SKELETON_AFTER_MS = 150
    const val LONG_TASK_MS = 2000
    fun isFast(ms: Int) = ms in 0..MAX_LATENCY_MS
}
