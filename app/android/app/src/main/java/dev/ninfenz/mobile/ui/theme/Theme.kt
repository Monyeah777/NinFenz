package dev.ninfenz.mobile.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import dev.ninfenz.mobile.ui.design.LocalNfSemantic
import dev.ninfenz.mobile.ui.design.NfColor
import dev.ninfenz.mobile.ui.design.NfShape
import dev.ninfenz.mobile.ui.design.NfType

/**
 * App 主题：颜色/排版/形状全部来自 ui.design 令牌。
 * dynamicColor 保留参数但不再启用：品牌色必须稳定，不能随壁纸漂移。
 */
@Composable
fun NfTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    @Suppress("UNUSED_PARAMETER") dynamicColor: Boolean = false,
    content: @Composable () -> Unit
) {
    CompositionLocalProvider(LocalNfSemantic provides NfColor.semantic(darkTheme)) {
        MaterialTheme(
            colorScheme = if (darkTheme) NfColor.dark() else NfColor.light(),
            typography = NfType.typography,
            shapes = NfShape.shapes,
            content = content
        )
    }
}
