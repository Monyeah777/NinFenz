package dev.ninfenz.mobile.ui.design

/**
 * NF 视觉令牌（纯数据，无 Compose 依赖，可被 JVM 单测直接读取）。
 *
 * 纪律：每个令牌必须带 source；S5（NF 推导）必须带公式/理由。
 * 标准源登记见 [Sources]，对应 sources.json 与《NF-视觉体系-标准源》。
 */
enum class SourceKind { S1, S2, S3, S4, S5, S6 }

data class SourceRef(
    val id: String,
    val kind: SourceKind,
    val note: String,
    val url: String? = null
)

object Sources {
    val WCAG_CONTRAST = SourceRef(
        "wcag-1.4.3", SourceKind.S1,
        "WCAG 2.2 1.4.3：正文 ≥4.5:1，大字 ≥3:1",
        "https://www.w3.org/TR/WCAG22/"
    )
    val WCAG_NONTEXT = SourceRef(
        "wcag-1.4.11", SourceKind.S1,
        "WCAG 2.2 1.4.11：非文本对比 ≥3:1",
        "https://www.w3.org/TR/WCAG22/"
    )
    val WCAG_RESIZE = SourceRef(
        "wcag-1.4.4", SourceKind.S1,
        "WCAG 2.2 1.4.4：文本可放大到 200%",
        "https://www.w3.org/TR/WCAG22/"
    )
    val ANDROID_TOUCH = SourceRef(
        "android-48dp", SourceKind.S2,
        "Android 无障碍：触控目标 ≥48dp（输入层自动扩展）",
        "https://developer.android.com/guide/topics/ui/accessibility/apps"
    )
    val M3_TYPE = SourceRef(
        "m3.type", SourceKind.S2,
        "Material 3 字阶：22/28、16/24、14/20、12/16（Compose 1.3.2 产物核对）",
        "https://m3.material.io/styles/typography"
    )
    val M3_SHAPE = SourceRef(
        "m3.shape", SourceKind.S2,
        "Material 3 圆角阶：4/8/12/16/28/full",
        "https://m3.material.io/styles/shape/corner-radius-scale"
    )
    val M3_ELEVATION = SourceRef(
        "m3.elevation", SourceKind.S2,
        "Material 3 层级 0–5，深色用 tonal elevation",
        "https://m3.material.io/styles/elevation"
    )
    val M3_MOTION = SourceRef(
        "m3.motion", SourceKind.S2,
        "Material 3 时长档位 150/250/300ms",
        "https://m3.material.io/styles/motion"
    )
    val M3_BREAKPOINTS = SourceRef(
        "m3.breakpoints", SourceKind.S2,
        "Material 3 窗口断点 600/840/1200/1600",
        "https://m3.material.io/foundations/layout/breakpoints/overview"
    )
    val M3_LIST = SourceRef(
        "m3.list", SourceKind.S2,
        "Material 3 列表行高 56/72/88",
        "https://m3.material.io/components/lists"
    )
    val M3_BUTTON = SourceRef(
        "m3.button", SourceKind.S2,
        "Material 3 按钮容器高 40dp",
        "https://m3.material.io/components/buttons"
    )
    val M3_NAV = SourceRef(
        "m3.nav", SourceKind.S2,
        "Material 3 导航栏 80dp",
        "https://m3.material.io/components/navigation-bar"
    )
    val M3_APPBAR = SourceRef(
        "m3.appbar", SourceKind.S2,
        "Material 3 小顶栏 64dp",
        "https://m3.material.io/components/top-app-bar"
    )
    val CARBON_GRID = SourceRef(
        "carbon.2x", SourceKind.S3,
        "IBM Carbon 2x Grid：8px 基本单元",
        "https://carbondesignsystem.com/building-blocks/foundations/2x-grid/overview"
    )
    val POLARIS_SPACE = SourceRef(
        "polaris.space", SourceKind.S3,
        "Shopify Polaris 间距以 4px 为基数",
        "https://polaris-react.shopify.com/design/layout/layout-tokens"
    )
    val BUTTERICK_LINE = SourceRef(
        "butterick.line", SourceKind.S4,
        "行宽 45–90 字符（含空格）",
        "https://practicaltypography.com/line-length.html"
    )
    val CLREQ = SourceRef(
        "w3c.clreq", SourceKind.S4,
        "W3C 中文排版需求：行首行尾禁则、字距；不含行距数值",
        "https://www.w3.org/TR/clreq/"
    )
    val CN_TYPE_SIZE = SourceRef(
        "cn.type-size", SourceKind.S4,
        "中文字号惯例：五号 10.5pt、小四 12pt"
    )
    val NF_BRAND_NEUTRAL = SourceRef(
        "nf.brand-hue", SourceKind.S5,
        "中性色色相锁定品牌青 168±10°；实测 0.2.0 底栏 250° 越界"
    )
    val NF_MONO = SourceRef(
        "nf.mono", SourceKind.S5,
        "哈希/路径等宽；无对应 M3 角色"
    )
    val NF_TRUST = SourceRef(
        "nf.trust", SourceKind.S5,
        "信任刻度 5 段对应 T0–T4"
    )
    val NF_MAX_WIDTH = SourceRef(
        "nf.max-width", SourceKind.S5,
        "内容限宽 720dp：840 断点下居中，控制中文行宽"
    )
    val NF_DENSITY = SourceRef(
        "nf.density", SourceKind.S5,
        "紧凑密度 = 间距 ×0.75，字号不变（M3 无此档）"
    )
    val MEASURED_020 = SourceRef(
        "measured.0.2.0", SourceKind.S6,
        "0.2.0 实机取样：底栏 #201F25、深色背景 #0F1413"
    )

    val all: List<SourceRef> = listOf(
        WCAG_CONTRAST, WCAG_NONTEXT, WCAG_RESIZE, ANDROID_TOUCH,
        M3_TYPE, M3_SHAPE, M3_ELEVATION, M3_MOTION, M3_BREAKPOINTS,
        M3_LIST, M3_BUTTON, M3_NAV, M3_APPBAR,
        CARBON_GRID, POLARIS_SPACE, BUTTERICK_LINE, CLREQ, CN_TYPE_SIZE,
        NF_BRAND_NEUTRAL, NF_MONO, NF_TRUST, NF_MAX_WIDTH, NF_DENSITY,
        MEASURED_020
    )
}

/** 字号令牌：size/line 单位 sp，tracking 单位 sp。 */
data class TypeToken(
    val name: String,
    val size: Float,
    val line: Float,
    val weight: Int,
    val tracking: Float,
    val source: SourceRef,
    val derivedBy: String? = null
)

object TypeScale {
    val screenTitle = TypeToken(
        "title.screen", 22f, 28f, 600, 0f, Sources.M3_TYPE,
        derivedBy = "D-01：titleLarge 字重 400→600，保证一屏唯一锚点"
    )
    val sectionTitle = TypeToken(
        "title.section", 16f, 24f, 600, 0f, Sources.M3_TYPE,
        derivedBy = "D-01：titleMedium 字重 500→600"
    )
    val itemTitle = TypeToken(
        "title.item", 16f, 24f, 500, 0f, Sources.M3_TYPE,
        derivedBy = "D-02：titleMedium 字距 0.15→0（中文）"
    )
    val body = TypeToken(
        "body", 16f, 24f, 400, 0f, Sources.M3_TYPE,
        derivedBy = "D-02：bodyLarge 字距 0.5→0（中文）"
    )
    val bodyLong = TypeToken(
        "body.long", 16f, 28f, 400, 0f, Sources.M3_TYPE,
        derivedBy = "长文行高 24→28（1.75），D-02 字距归零"
    )
    val label = TypeToken(
        "label", 14f, 20f, 500, 0f, Sources.M3_TYPE,
        derivedBy = "D-02：labelLarge 字距 0.1→0"
    )
    val secondary = TypeToken(
        "body.secondary", 14f, 20f, 400, 0f, Sources.M3_TYPE,
        derivedBy = "D-02：bodyMedium 字距 0.2→0"
    )
    val meta = TypeToken(
        "meta", 12f, 20f, 400, 0f, Sources.M3_TYPE,
        derivedBy = "D-03：bodySmall 行高 16→20（中文 1.67），字距归零"
    )
    val mono = TypeToken(
        "mono", 12f, 20f, 400, 0f, Sources.NF_MONO,
        derivedBy = "D-05：哈希/路径必须等宽，无 M3 对应角色"
    )

    val all: List<TypeToken> = listOf(
        screenTitle, sectionTitle, itemTitle, body, bodyLong, label, secondary, meta, mono
    )

    /** 只允许这四个字号出现（等宽复用 12）。 */
    val allowedSizes: Set<Float> = setOf(22f, 16f, 14f, 12f)
}

/** 颜色令牌：light/dark 均为 ARGB。 */
data class ColorToken(
    val name: String,
    val light: Int,
    val dark: Int,
    val source: SourceRef
)

object Palette {
    val background = ColorToken("surface.base", 0xFFF7FAF9.toInt(), 0xFF0F1413.toInt(), Sources.NF_BRAND_NEUTRAL)
    val surface = ColorToken("surface.card", 0xFFFFFFFF.toInt(), 0xFF1B2725.toInt(), Sources.NF_BRAND_NEUTRAL)
    val surfaceRaised = ColorToken("surface.raised", 0xFFFFFFFF.toInt(), 0xFF2A3734.toInt(), Sources.NF_BRAND_NEUTRAL)
    val surfaceVariant = ColorToken("surface.variant", 0xFFE6EDEB.toInt(), 0xFF34433F.toInt(), Sources.NF_BRAND_NEUTRAL)
    val onSurface = ColorToken("text.primary", 0xFF14181A.toInt(), 0xFFE3E9E7.toInt(), Sources.WCAG_CONTRAST)
    val onSurfaceVariant = ColorToken("text.secondary", 0xFF46524F.toInt(), 0xFFA9B6B3.toInt(), Sources.WCAG_CONTRAST)
    val outline = ColorToken("outline", 0xFF6B7A77.toInt(), 0xFF6E7B78.toInt(), Sources.WCAG_NONTEXT)
    val outlineVariant = ColorToken("outline.variant", 0xFFC9D4D1.toInt(), 0xFF3A4744.toInt(), Sources.NF_BRAND_NEUTRAL)
    val primary = ColorToken("brand.primary", 0xFF1E5F5B.toInt(), 0xFF9BD0CB.toInt(), Sources.NF_BRAND_NEUTRAL)
    val onPrimary = ColorToken("brand.on-primary", 0xFFFFFFFF.toInt(), 0xFF003733.toInt(), Sources.WCAG_CONTRAST)
    val primaryContainer = ColorToken("brand.container", 0xFFB7E4DF.toInt(), 0xFF00504B.toInt(), Sources.NF_BRAND_NEUTRAL)
    val onPrimaryContainer = ColorToken("brand.on-container", 0xFF003733.toInt(), 0xFFB7E4DF.toInt(), Sources.WCAG_CONTRAST)
    val error = ColorToken("status.error", 0xFFB3261E.toInt(), 0xFFF2B8B5.toInt(), Sources.WCAG_CONTRAST)
    val onError = ColorToken("status.on-error", 0xFFFFFFFF.toInt(), 0xFF3B0907.toInt(), Sources.WCAG_CONTRAST)
    val errorContainer = ColorToken("status.error-container", 0xFFF9DEDC.toInt(), 0xFF8C1D18.toInt(), Sources.WCAG_CONTRAST)
    val onErrorContainer = ColorToken("status.on-error-container", 0xFF410E0B.toInt(), 0xFFF2B8B5.toInt(), Sources.WCAG_CONTRAST)
    val success = ColorToken("status.success", 0xFF1B6B47.toInt(), 0xFFA5D6B8.toInt(), Sources.WCAG_CONTRAST)
    val onSuccess = ColorToken("status.on-success", 0xFFFFFFFF.toInt(), 0xFF06281A.toInt(), Sources.WCAG_CONTRAST)
    val successContainer = ColorToken("status.success-container", 0xFFE3F2E8.toInt(), 0xFF0E3A24.toInt(), Sources.WCAG_CONTRAST)
    val onSuccessContainer = ColorToken("status.on-success-container", 0xFF0B3A22.toInt(), 0xFFA5D6B8.toInt(), Sources.WCAG_CONTRAST)
    val warning = ColorToken("status.warning", 0xFF7A4A00.toInt(), 0xFFFFD9A0.toInt(), Sources.WCAG_CONTRAST)
    val onWarning = ColorToken("status.on-warning", 0xFFFFFFFF.toInt(), 0xFF3A2500.toInt(), Sources.WCAG_CONTRAST)
    val warningContainer = ColorToken("status.warning-container", 0xFFFFF3E0.toInt(), 0xFF4A2E00.toInt(), Sources.WCAG_CONTRAST)
    val onWarningContainer = ColorToken("status.on-warning-container", 0xFF3D2500.toInt(), 0xFFFFD9A0.toInt(), Sources.WCAG_CONTRAST)
    val info = ColorToken("status.info", 0xFF1B4F8A.toInt(), 0xFFA8C8F0.toInt(), Sources.WCAG_CONTRAST)
    val onInfo = ColorToken("status.on-info", 0xFFFFFFFF.toInt(), 0xFF0A2440.toInt(), Sources.WCAG_CONTRAST)
    val infoContainer = ColorToken("status.info-container", 0xFFE4EEF9.toInt(), 0xFF10365E.toInt(), Sources.WCAG_CONTRAST)
    val onInfoContainer = ColorToken("status.on-info-container", 0xFF0B2A4A.toInt(), 0xFFA8C8F0.toInt(), Sources.WCAG_CONTRAST)
    val scrim = ColorToken("scrim", 0x00000000.toInt(), 0x00000000.toInt(), Sources.M3_ELEVATION)

    val all: List<ColorToken> = listOf(
        background, surface, surfaceRaised, surfaceVariant, onSurface, onSurfaceVariant,
        outline, outlineVariant, primary, onPrimary, primaryContainer, onPrimaryContainer,
        error, onError, errorContainer, onErrorContainer,
        success, onSuccess, successContainer, onSuccessContainer,
        warning, onWarning, warningContainer, onWarningContainer,
        info, onInfo, infoContainer, onInfoContainer, scrim
    )
}

/** 对比度验收对：fg/bg + 最低比值（WCAG）。 */
data class ContrastPair(
    val name: String,
    val fg: ColorToken,
    val bg: ColorToken,
    val min: Double
)

object ContrastPairs {
    val all: List<ContrastPair> = listOf(
        ContrastPair("正文/背景", Palette.onSurface, Palette.background, 4.5),
        ContrastPair("正文/卡片", Palette.onSurface, Palette.surface, 4.5),
        ContrastPair("次文/背景", Palette.onSurfaceVariant, Palette.background, 4.5),
        ContrastPair("次文/卡片", Palette.onSurfaceVariant, Palette.surface, 4.5),
        ContrastPair("次文/变体底", Palette.onSurfaceVariant, Palette.surfaceVariant, 4.5),
        ContrastPair("品牌文字/背景", Palette.primary, Palette.background, 4.5),
        ContrastPair("反白/品牌", Palette.onPrimary, Palette.primary, 4.5),
        ContrastPair("反白/品牌容器", Palette.onPrimaryContainer, Palette.primaryContainer, 4.5),
        ContrastPair("错误/背景", Palette.error, Palette.background, 4.5),
        ContrastPair("反白/错误", Palette.onError, Palette.error, 4.5),
        ContrastPair("反白/成功", Palette.onSuccess, Palette.success, 4.5),
        ContrastPair("反白/警告", Palette.onWarning, Palette.warning, 4.5),
        ContrastPair("反白/信息", Palette.onInfo, Palette.info, 4.5),
        ContrastPair("错误容器文字", Palette.onErrorContainer, Palette.errorContainer, 4.5),
        ContrastPair("成功容器文字", Palette.onSuccessContainer, Palette.successContainer, 4.5),
        ContrastPair("警告容器文字", Palette.onWarningContainer, Palette.warningContainer, 4.5),
        ContrastPair("信息容器文字", Palette.onInfoContainer, Palette.infoContainer, 4.5),
        ContrastPair("描边/背景", Palette.outline, Palette.background, 3.0),
        ContrastPair("描边/卡片", Palette.outline, Palette.surface, 3.0)
    )
}

/** 间距：4 的倍数，8 的节奏。 */
object Space {
    const val inline = 4
    const val gap = 8
    const val itemGap = 12
    const val gutter = 16
    const val section = 24
    const val page = 32
    const val hero = 48
    val all = listOf(inline, gap, itemGap, gutter, section, page, hero)
}

object Radius {
    const val xs = 4
    const val sm = 8
    const val md = 12
    const val lg = 16
    const val xl = 28
    const val full = 999
    val all = listOf(xs, sm, md, lg, xl, full)
}

object Motion {
    const val fast = 150
    const val base = 250
    const val slow = 300
    val all = listOf(fast, base, slow)
}

object Sizes {
    const val touchTarget = 48
    const val topAppBar = 64
    const val button = 40
    const val textField = 56
    const val listOneLine = 56
    const val listTwoLine = 72
    const val navigationBar = 80
    const val iconInline = 18
    const val iconDefault = 20
    const val iconNav = 24
    const val focusRing = 2
}

object Layout {
    const val gutter = 16
    const val maxContentWidth = 720
    const val breakpointMedium = 600
    const val breakpointExpanded = 840
    const val breakpointLarge = 1200
    const val compactFactor = 0.75
}
