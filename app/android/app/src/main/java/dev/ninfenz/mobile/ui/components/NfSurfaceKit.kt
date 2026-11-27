package dev.ninfenz.mobile.ui.components

import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import dev.ninfenz.mobile.ui.theme.NfMotion
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.ui.theme.NfSpacing

/**
 * 列表展开/收起动画与底部动作条容器（Library 与 WorkflowHub/Import 共用）。
 *
 * 审计规则 D-002：同一段 8 行块此前在多个 screen 里复制；统一到这里，参数值只有一处。
 */
fun nfExpandableEnter(): EnterTransition =
    fadeIn(tween(NfMotion.SHORT_MS)) + expandVertically(
        animationSpec = spring(dampingRatio = 0.82f, stiffness = 420f),
        expandFrom = Alignment.Top
    )

fun nfExpandableExit(): ExitTransition =
    fadeOut(tween(NfMotion.SHORT_MS)) + shrinkVertically(
        animationSpec = spring(dampingRatio = 0.9f, stiffness = 500f),
        shrinkTowards = Alignment.Top
    )

/** 底部动作条容器：横贯页面的 Surface + 单行内容（撤销/已清理提示等）。 */
@Composable
fun NfActionBarSurface(content: @Composable RowScope.() -> Unit) {
    Surface(
        modifier = Modifier.padding(horizontal = NfSpacing.page, vertical = NfSpacing.m),
        shape = MaterialTheme.shapes.large,
        tonalElevation = 6.dp
    ) {
        Row(
            modifier = Modifier.padding(horizontal = NfSpacing.m, vertical = NfSpacing.xs),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(NfSpacing.s),
            content = content
        )
    }
}
