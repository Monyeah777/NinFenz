package dev.ninfenz.mobile.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

/** NF 间距刻度：4dp 基准（§18.2）。 */
object NfSpacing {
    val xs = 4.dp
    val s = 8.dp
    val m = 12.dp
    val l = 16.dp
    val xl = 24.dp
    val xxl = 32.dp
    val xxxl = 48.dp
    val page = 16.dp
}

/** NF 形状：4/8/12/16/24/full（§17.6）。 */
val NfShapes = Shapes(
    extraSmall = RoundedCornerShape(4.dp),
    small = RoundedCornerShape(8.dp),
    medium = RoundedCornerShape(12.dp),
    large = RoundedCornerShape(16.dp),
    extraLarge = RoundedCornerShape(24.dp)
)

/** 动效 token（§17.2/§17.13）：只暴露实现需要的值。 */
object NfMotion {
    const val SHORT_MS = 120
    const val MEDIUM_MS = 220
    const val LONG_MS = 320
    const val PRESS_DOWN_MS = 90
    const val PRESS_DAMPING = 0.7f
    const val PRESS_STIFFNESS = 500f
}

/** 语义状态色（v0.02 先给容器色；图标+文字在组件层成对使用）。 */
object NfStatusColors {
    const val SUCCESS = 0xFF2E7D32
    const val WARN = 0xFFB26A00
    const val INFO = 0xFF1565C0
}
