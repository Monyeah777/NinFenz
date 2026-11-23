package dev.ninfenz.mobile.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import dev.ninfenz.mobile.ui.design.LocalNfSemantic
import dev.ninfenz.mobile.ui.design.NfColor
import dev.ninfenz.mobile.ui.design.NfShape
import dev.ninfenz.mobile.ui.design.NfType

/** Opt-in theme for the visual-system preview; default app theme stays unchanged until screen migration. */
@Composable
fun NfDesignTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
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
