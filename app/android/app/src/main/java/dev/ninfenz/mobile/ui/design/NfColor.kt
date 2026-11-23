package dev.ninfenz.mobile.ui.design

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

/** M3 没有成功/警告/信息三组语义色，这里显式补上，避免组件里写死浅色值。 */
@Immutable
data class NfSemanticColors(
    val successContainer: Color,
    val onSuccessContainer: Color,
    val warningContainer: Color,
    val onWarningContainer: Color,
    val infoContainer: Color,
    val onInfoContainer: Color
)

val LocalNfSemantic = staticCompositionLocalOf {
    NfSemanticColors(
        successContainer = Color(0xFFE3F2E8),
        onSuccessContainer = Color(0xFF0B3A22),
        warningContainer = Color(0xFFFFF3E0),
        onWarningContainer = Color(0xFF3D2500),
        infoContainer = Color(0xFFE4EEF9),
        onInfoContainer = Color(0xFF0B2A4A)
    )
}

/**
 * 全角色配色。
 *
 * 只覆盖 8 个角色的后果在 0.2.0 实测可见：底栏落到 M3 默认 surfaceContainer #211F26，
 * 色相 250°，与品牌 168–174° 相差 76–82°。这里把容器/描边/表面全部显式给出。
 */
object NfColor {

    private fun color(token: ColorToken, dark: Boolean): Color =
        Color(if (dark) token.dark else token.light)

    fun semantic(dark: Boolean): NfSemanticColors = NfSemanticColors(
        successContainer = color(Palette.successContainer, dark),
        onSuccessContainer = color(Palette.onSuccessContainer, dark),
        warningContainer = color(Palette.warningContainer, dark),
        onWarningContainer = color(Palette.onWarningContainer, dark),
        infoContainer = color(Palette.infoContainer, dark),
        onInfoContainer = color(Palette.onInfoContainer, dark)
    )

    fun light(): ColorScheme = lightColorScheme(
        primary = color(Palette.primary, false),
        onPrimary = color(Palette.onPrimary, false),
        primaryContainer = color(Palette.primaryContainer, false),
        onPrimaryContainer = color(Palette.onPrimaryContainer, false),
        inversePrimary = color(Palette.primaryContainer, false),
        secondary = color(Palette.onSurfaceVariant, false),
        onSecondary = color(Palette.surface, false),
        secondaryContainer = color(Palette.surfaceVariant, false),
        onSecondaryContainer = color(Palette.onSurface, false),
        tertiary = color(Palette.info, false),
        onTertiary = color(Palette.onInfo, false),
        tertiaryContainer = color(Palette.infoContainer, false),
        onTertiaryContainer = color(Palette.onInfoContainer, false),
        background = color(Palette.background, false),
        onBackground = color(Palette.onSurface, false),
        surface = color(Palette.surface, false),
        onSurface = color(Palette.onSurface, false),
        surfaceVariant = color(Palette.surfaceVariant, false),
        onSurfaceVariant = color(Palette.onSurfaceVariant, false),
        surfaceTint = color(Palette.primary, false),
        inverseSurface = color(Palette.onSurface, false),
        inverseOnSurface = color(Palette.background, false),
        error = color(Palette.error, false),
        onError = color(Palette.onError, false),
        errorContainer = color(Palette.errorContainer, false),
        onErrorContainer = color(Palette.onErrorContainer, false),
        outline = color(Palette.outline, false),
        outlineVariant = color(Palette.outlineVariant, false),
        scrim = Color.Black,
        surfaceBright = color(Palette.background, false),
        surfaceDim = color(Palette.surfaceVariant, false),
        surfaceContainerLowest = color(Palette.surface, false),
        surfaceContainerLow = color(Palette.background, false),
        surfaceContainer = color(Palette.surface, false),
        surfaceContainerHigh = color(Palette.surfaceRaised, false),
        surfaceContainerHighest = color(Palette.surfaceVariant, false)
    )

    fun dark(): ColorScheme = darkColorScheme(
        primary = color(Palette.primary, true),
        onPrimary = color(Palette.onPrimary, true),
        primaryContainer = color(Palette.primaryContainer, true),
        onPrimaryContainer = color(Palette.onPrimaryContainer, true),
        inversePrimary = color(Palette.primaryContainer, true),
        secondary = color(Palette.onSurfaceVariant, true),
        onSecondary = color(Palette.background, true),
        secondaryContainer = color(Palette.surfaceVariant, true),
        onSecondaryContainer = color(Palette.onSurface, true),
        tertiary = color(Palette.info, true),
        onTertiary = color(Palette.onInfo, true),
        tertiaryContainer = color(Palette.infoContainer, true),
        onTertiaryContainer = color(Palette.onInfoContainer, true),
        background = color(Palette.background, true),
        onBackground = color(Palette.onSurface, true),
        surface = color(Palette.background, true),
        onSurface = color(Palette.onSurface, true),
        surfaceVariant = color(Palette.surfaceVariant, true),
        onSurfaceVariant = color(Palette.onSurfaceVariant, true),
        surfaceTint = color(Palette.primary, true),
        inverseSurface = color(Palette.onSurface, true),
        inverseOnSurface = color(Palette.background, true),
        error = color(Palette.error, true),
        onError = color(Palette.onError, true),
        errorContainer = color(Palette.errorContainer, true),
        onErrorContainer = color(Palette.onErrorContainer, true),
        outline = color(Palette.outline, true),
        outlineVariant = color(Palette.outlineVariant, true),
        scrim = Color.Black,
        surfaceBright = color(Palette.surfaceRaised, true),
        surfaceDim = color(Palette.background, true),
        surfaceContainerLowest = color(Palette.background, true),
        surfaceContainerLow = color(Palette.surface, true),
        surfaceContainer = color(Palette.surface, true),
        surfaceContainerHigh = color(Palette.surfaceRaised, true),
        surfaceContainerHighest = color(Palette.surfaceVariant, true)
    )
}
