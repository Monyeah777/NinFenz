package dev.ninfenz.mobile.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val Light = lightColorScheme(
    primary = Color(0xFF1E5F5B),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFB7E4DF),
    secondary = Color(0xFF4A6360),
    background = Color(0xFFF7FAF9),
    surface = Color(0xFFF7FAF9),
    error = Color(0xFFB3261E)
)

private val Dark = darkColorScheme(
    primary = Color(0xFF9BD0CB),
    onPrimary = Color(0xFF003733),
    primaryContainer = Color(0xFF00504B),
    secondary = Color(0xFFB1CCC8),
    background = Color(0xFF0F1413),
    surface = Color(0xFF0F1413)
)

@Composable
fun NfTheme(darkTheme: Boolean = false, content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (darkTheme) Dark else Light,
        typography = Typography(),
        content = content
    )
}
