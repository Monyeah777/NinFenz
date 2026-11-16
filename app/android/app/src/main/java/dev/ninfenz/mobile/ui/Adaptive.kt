package dev.ninfenz.mobile.ui

import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalWindowInfo
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.R
import dev.ninfenz.mobile.state.Screen

/** 窗口宽度分档（Material3 WindowSizeClass 的等价实现，纯函数可单测）。 */
enum class LayoutClass { COMPACT, MEDIUM, EXPANDED }

fun layoutClassFor(widthDp: Int): LayoutClass = when {
    widthDp < 600 -> LayoutClass.COMPACT
    widthDp < 840 -> LayoutClass.MEDIUM
    else -> LayoutClass.EXPANDED
}

@Composable
fun currentWindowWidthDp(): Int {
    val pixels = LocalWindowInfo.current.containerSize.width
    return with(LocalDensity.current) { pixels.toDp().value.toInt() }
}

@Composable
fun currentLayoutClass(): LayoutClass = layoutClassFor(currentWindowWidthDp())

/** 屏幕标签的字符串资源（无障碍朗读用；与 title 的英文内部名分离）。 */
fun screenLabelRes(screen: Screen): Int = when (screen) {
    Screen.HOME -> R.string.screen_home
    Screen.IMPORT -> R.string.screen_import
    Screen.PROTOCOL -> R.string.screen_protocol
    Screen.GRAPH -> R.string.screen_graph
    Screen.ASSEMBLY -> R.string.screen_assembly
    Screen.PACK_UPDATE -> R.string.screen_pack_update
    Screen.CCOS -> R.string.screen_ccos
    Screen.SETTINGS -> R.string.screen_settings
}

/** 纯函数中文标签：仅供非 Compose 单测/诊断使用；界面走 screenLabelRes。 */
fun screenLabel(screen: Screen): String = when (screen) {
    Screen.HOME -> "首页"
    Screen.IMPORT -> "导入"
    Screen.PROTOCOL -> "协议"
    Screen.GRAPH -> "管线"
    Screen.ASSEMBLY -> "装配"
    Screen.PACK_UPDATE -> "Pack 更新"
    Screen.CCOS -> "CCOS"
    Screen.SETTINGS -> "设置"
}

/**
 * 中等/扩展宽度下的常驻导航栏（折叠展开/平板/Chromebook/多窗口）。
 * 图标用中文首字并清空语义，避免 TalkBack 重复朗读（标签已可读）。
 */
@Composable
fun AdaptiveNavigationRail(current: Screen, onSelect: (Screen) -> Unit) {
    NavigationRail {
        Screen.entries.forEach { screen ->
            NavigationRailItem(
                selected = screen == current,
                onClick = { onSelect(screen) },
                icon = {
                    Text(
                        stringResource(screenLabelRes(screen)).take(1),
                        modifier = Modifier.clearAndSetSemantics { }
                    )
                },
                label = { Text(stringResource(screenLabelRes(screen))) }
            )
        }
    }
}
