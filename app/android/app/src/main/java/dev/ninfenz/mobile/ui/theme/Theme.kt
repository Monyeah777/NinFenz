package dev.ninfenz.mobile.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp


/** 品牌调色板（对比度单测的单一来源）。 */
object NfPalette {
    val LightPrimary = Color(0xFF1E5F5B)
    val LightOnPrimary = Color.White
    val LightBackground = Color(0xFFF7FAF9)
    val LightOnBackground = Color(0xFF1A1C1B)
    val LightSurface = Color(0xFFF7FAF9)
    val LightOnSurface = Color(0xFF1A1C1B)
    val LightError = Color(0xFFB3261E)
    val LightOnError = Color.White

    val DarkPrimary = Color(0xFF9BD0CB)
    val DarkOnPrimary = Color(0xFF003733)
    val DarkBackground = Color(0xFF0F1413)
    val DarkOnBackground = Color(0xFFE2E3E1)
    val DarkSurface = Color(0xFF0F1413)
    val DarkOnSurface = Color(0xFFE2E3E1)
    val DarkError = Color(0xFFF2B8B5)
    val DarkOnError = Color(0xFF601410)
}

private val Light = lightColorScheme(
    primary = NfPalette.LightPrimary,
    onPrimary = NfPalette.LightOnPrimary,
    primaryContainer = Color(0xFFB7E4DF),
    onPrimaryContainer = Color(0xFF00201D),
    secondary = Color(0xFF4A6360),
    secondaryContainer = Color(0xFFCCE8E4),
    onSecondaryContainer = Color(0xFF00201D),
    tertiary = Color(0xFF3F6375),
    background = NfPalette.LightBackground,
    onBackground = NfPalette.LightOnBackground,
    surface = NfPalette.LightSurface,
    onSurface = NfPalette.LightOnSurface,
    surfaceVariant = Color(0xFFDBE5E2),
    onSurfaceVariant = Color(0xFF3F4947),
    outline = Color(0xFF6F7977),
    error = NfPalette.LightError,
    onError = NfPalette.LightOnError
)

private val Dark = darkColorScheme(
    primary = NfPalette.DarkPrimary,
    onPrimary = NfPalette.DarkOnPrimary,
    primaryContainer = Color(0xFF00504B),
    onPrimaryContainer = Color(0xFFB7E4DF),
    secondary = Color(0xFFB1CCC8),
    secondaryContainer = Color(0xFF324B48),
    onSecondaryContainer = Color(0xFFCCE8E4),
    tertiary = Color(0xFFA7CBDF),
    background = NfPalette.DarkBackground,
    onBackground = NfPalette.DarkOnBackground,
    surface = NfPalette.DarkSurface,
    onSurface = NfPalette.DarkOnSurface,
    surfaceVariant = Color(0xFF3F4947),
    onSurfaceVariant = Color(0xFFBFC9C6),
    outline = Color(0xFF899390),
    error = NfPalette.DarkError,
    onError = NfPalette.DarkOnError
)

/** NF 7 档字体（§18.1）：中文行高 1.6–1.7，标题 600/正文 400。 */
val NfTypography = Typography(
    displaySmall = TextStyle(fontSize = 32.sp, lineHeight = 40.sp, fontWeight = FontWeight.SemiBold, letterSpacing = (-0.5).sp),
    headlineSmall = TextStyle(fontSize = 24.sp, lineHeight = 32.sp, fontWeight = FontWeight.SemiBold, letterSpacing = (-0.2).sp),
    titleLarge = TextStyle(fontSize = 20.sp, lineHeight = 28.sp, fontWeight = FontWeight.SemiBold),
    titleMedium = TextStyle(fontSize = 16.sp, lineHeight = 24.sp, fontWeight = FontWeight.Medium),
    bodyLarge = TextStyle(fontSize = 16.sp, lineHeight = 26.sp, fontWeight = FontWeight.Normal),
    bodyMedium = TextStyle(fontSize = 14.sp, lineHeight = 23.sp, fontWeight = FontWeight.Normal),
    bodySmall = TextStyle(fontSize = 12.sp, lineHeight = 19.sp, fontWeight = FontWeight.Normal),
    labelLarge = TextStyle(fontSize = 14.sp, lineHeight = 20.sp, fontWeight = FontWeight.Medium),
    labelMedium = TextStyle(fontSize = 12.sp, lineHeight = 16.sp, fontWeight = FontWeight.Medium),
    labelSmall = TextStyle(fontSize = 11.sp, lineHeight = 16.sp, fontWeight = FontWeight.Medium)
)

@Composable
fun NfTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit
) {
    val context = LocalContext.current
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ->
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        darkTheme -> Dark
        else -> Light
    }
    MaterialTheme(
        colorScheme = colorScheme,
        typography = NfTypography,
        shapes = NfShapes,
        content = content
    )
}
