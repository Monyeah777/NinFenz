package dev.ninfenz.mobile.ui.design

/** 非视觉感知：触觉、声音、读屏、减弱动效。 */
enum class HapticKind { CONFIRM, ERROR, SELECTION, NONE }

data class HapticSpec(val kind: HapticKind, val durationMs: Int, val amplitude: Int)

object Haptics {
    val confirm = HapticSpec(HapticKind.CONFIRM, 12, 80)
    val error = HapticSpec(HapticKind.ERROR, 24, 160)
    val selection = HapticSpec(HapticKind.SELECTION, 8, 60)
    val none = HapticSpec(HapticKind.NONE, 0, 0)

    fun forState(state: UiState): HapticSpec = when (state) {
        UiState.ERROR, UiState.EXPIRED -> error
        UiState.SIGNED, UiState.PARTIAL -> confirm
        UiState.EMPTY, UiState.LOADING, UiState.OFFLINE -> none
    }
}

object SoundPolicy {
    /** 默认无声；必须尊重系统静音/勿扰；不播放“成功音”作为唯一反馈。 */
    const val ENABLED_BY_DEFAULT = false
    const val RESPECT_SILENT = true
}

object Announcement {
    const val ERROR_POLITE = "assertive"
    const val STATUS_POLITE = "polite"

    fun forState(state: UiState): String? = when (state) {
        UiState.ERROR -> "错误：$state"
        UiState.PARTIAL -> "部分完成"
        UiState.SIGNED -> "已签收"
        UiState.EXPIRED -> "已过期"
        else -> null
    }
}

/** 键盘/IME/窗口：流式布局在这些边界不能遮住主操作。 */
object InsetsPolicy {
    const val IME_BOTTOM_PADDING = true
    const val CUTOUT_SAFE = true
    const val NAV_BAR_SAFE = true
    const val LANDSCAPE_MAX_CONTENT = Layout.maxContentWidth
}
