package dev.ninfenz.mobile.ui.design

import androidx.compose.material3.Typography
import androidx.compose.ui.text.PlatformTextStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.Hyphens
import androidx.compose.ui.text.style.LineBreak
import androidx.compose.ui.text.style.LineHeightStyle
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.sp

/**
 * 令牌 → Compose TextStyle。
 *
 * 微排版固定项：
 * - includeFontPadding=false：顶对齐可预测，不依赖字体自带留白。
 * - 正文 Trim.None / 标题 Trim.FirstLineTop：标题首行贴齐容器顶。
 * - 中文 tracking=0；断行交给系统（标题 Heading，正文 Paragraph）；不用两端对齐。
 */
object NfType {

    private fun TypeToken.style(
        lineBreak: LineBreak = LineBreak.Paragraph,
        trim: LineHeightStyle.Trim = LineHeightStyle.Trim.None,
        fontFamily: FontFamily = FontFamily.SansSerif
    ): TextStyle = TextStyle(
        fontFamily = fontFamily,
        fontSize = size.sp,
        lineHeight = line.sp,
        fontWeight = FontWeight(weight),
        letterSpacing = tracking.sp,
        textAlign = TextAlign.Start,
        lineBreak = lineBreak,
        hyphens = Hyphens.None,
        platformStyle = PlatformTextStyle(includeFontPadding = false),
        lineHeightStyle = LineHeightStyle(LineHeightStyle.Alignment.Center, trim)
    )

    val screenTitle: TextStyle =
        TypeScale.screenTitle.style(lineBreak = LineBreak.Heading, trim = LineHeightStyle.Trim.FirstLineTop)
    val sectionTitle: TextStyle =
        TypeScale.sectionTitle.style(lineBreak = LineBreak.Heading, trim = LineHeightStyle.Trim.FirstLineTop)
    val itemTitle: TextStyle =
        TypeScale.itemTitle.style(lineBreak = LineBreak.Heading, trim = LineHeightStyle.Trim.FirstLineTop)
    val body: TextStyle = TypeScale.body.style()
    val bodyLong: TextStyle = TypeScale.bodyLong.style()
    val label: TextStyle = TypeScale.label.style()
    val secondary: TextStyle = TypeScale.secondary.style()
    val meta: TextStyle = TypeScale.meta.style()
    val mono: TextStyle = TypeScale.mono.style(fontFamily = FontFamily.Monospace)

    /** 关键数字：等宽数字，避免计数跳动。 */
    val numeric: TextStyle = body.copy(
        fontWeight = FontWeight(600),
        fontFeatureSettings = "tnum"
    )

    val typography: Typography = Typography(
        displayLarge = screenTitle,
        displayMedium = screenTitle,
        displaySmall = screenTitle,
        headlineLarge = screenTitle,
        headlineMedium = screenTitle,
        headlineSmall = screenTitle,
        titleLarge = screenTitle,
        titleMedium = itemTitle,
        titleSmall = label,
        bodyLarge = body,
        bodyMedium = secondary,
        bodySmall = meta,
        labelLarge = label,
        labelMedium = meta,
        labelSmall = meta
    )
}
