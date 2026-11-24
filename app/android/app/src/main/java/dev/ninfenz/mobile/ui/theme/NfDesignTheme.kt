package dev.ninfenz.mobile.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.Composable

/** 兼容入口：设计系统预览与默认主题共用同一实现，避免双主题漂移。 */
@Composable
fun NfDesignTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    NfTheme(darkTheme = darkTheme, dynamicColor = false, content = content)
}
