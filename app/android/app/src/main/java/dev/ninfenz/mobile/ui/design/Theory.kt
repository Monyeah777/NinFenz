package dev.ninfenz.mobile.ui.design

/**
 * 视觉理论到令牌/组件的可审计映射。
 *
 * 这不是“理论摘抄”：每条规则都必须指向已存在的令牌或组件，并在
 * VisualTheoryTest 中检查覆盖；没有对应实现的理论不进入本表。
 */
data class TheoryRule(
    val id: String,
    val tradition: String,
    val construct: String,
    val token: String,
    val rule: String,
    val source: String
)

data class QualityMetric(
    val id: String,
    val quality: String,
    val question: String,
    val evidence: String,
    val target: String,
    val instrumented: Boolean
)

object VisualTheory {

    // ---- 格式塔：组织律 ----
    val proximity = TheoryRule(
        "G-PROX", "Gestalt", "proximity", "Space.itemGap < Space.section",
        "组内间距必须小于组间间距；分组先靠留白，不先加卡片。",
        "Wertheimer 1923; Koffka 1935"
    )
    val similarity = TheoryRule(
        "G-SIM", "Gestalt", "similarity", "Palette.primary + TypeScale",
        "同类元素共享同一形状/字号/颜色；品牌强调色只有一组。",
        "Wertheimer 1923"
    )
    val continuity = TheoryRule(
        "G-CONT", "Gestalt", "continuity", "Layout.gutter + 4dp grid",
        "同一阅读轴上的元素对齐；不无故换轴、不突然缩进。",
        "Wertheimer 1923"
    )
    val closure = TheoryRule(
        "G-CLOS", "Gestalt", "closure", "NfStatusChip / NfTrustMeter",
        "状态必须能被补全为完整语义：文字 + 形状 + 颜色 + 图标/圆点。",
        "Wertheimer 1923"
    )
    val figureGround = TheoryRule(
        "G-FG", "Gestalt", "figure-ground", "Palette.surface ladder",
        "主体与背景用明度阶梯分离；深色不用阴影伪造层级。",
        "Rubin 1915; M3 elevation"
    )
    val commonFate = TheoryRule(
        "G-FATE", "Gestalt", "common-fate", "Motion.fast/base/slow",
        "同组元素共享同一动效时长与方向；不同组不共享动势。",
        "Wertheimer 1923"
    )

    // ---- Bertin：视觉变量 ----
    val position = TheoryRule(
        "B-POS", "Bertin", "position", "Layout + Space",
        "位置编码顺序与层级：标题→内容→动作；不随机放置主操作。",
        "Bertin 1967, Sémiologie graphique"
    )
    val size = TheoryRule(
        "B-SIZE", "Bertin", "size", "TypeScale / Sizes.icon*",
        "大小编码重要性：22/16/14/12 四级；图标 18/20/24 三档。",
        "Bertin 1967"
    )
    val shape = TheoryRule(
        "B-SHAPE", "Bertin", "shape", "Radius / NfShape",
        "形状编码类别：pill=动作，12=卡片，8=输入，4=内联标记。",
        "Bertin 1967; M3 shape"
    )
    val value = TheoryRule(
        "B-VALUE", "Bertin", "value", "Palette.surface/raised/variant",
        "明度编码深度：0 底、1 卡、2 抬升、3 变体；不叠阴影。",
        "Bertin 1967; M3 tonal elevation"
    )
    val hue = TheoryRule(
        "B-HUE", "Bertin", "hue", "Palette.primary + status.*",
        "色相编码语义：品牌青只表品牌/主操作；状态色只表状态。",
        "Bertin 1967; WCAG 1.4.1"
    )
    val orientation = TheoryRule(
        "B-ORIENT", "Bertin", "orientation", "18/20/24 icon grid",
        "方向编码动作：返回/前进/展开的箭头方向必须与行为一致。",
        "Bertin 1967"
    )
    val texture = TheoryRule(
        "B-TEX", "Bertin", "texture", "no texture in core; patterns for viz",
        "核心界面不用纹理冒充层级；图表需非颜色编码时才用纹理/点线。",
        "Bertin 1967; WCAG 1.4.1"
    )

    // ---- Kress & van Leeuwen：视觉语法 ----
    val informationValue = TheoryRule(
        "K-INFO", "Kress & van Leeuwen", "information-value",
        "top bar + label/value rows + primary action",
        "上=理想/标题，下=现实/内容；左=已知标签，右=新值；中心=主任务。",
        "Kress & van Leeuwen 2006, Reading Images"
    )
    val salience = TheoryRule(
        "K-SAL", "Kress & van Leeuwen", "salience",
        "one filled button + brand primary",
        "一屏一个填充主操作；显著性来自对比/面积/位置，不靠堆色。",
        "Kress & van Leeuwen 2006"
    )
    val framing = TheoryRule(
        "K-FRAME", "Kress & van Leeuwen", "framing",
        "card + Space.section",
        "框架表达范畴：卡片切分对象，留白切分组；不嵌套卡片。",
        "Kress & van Leeuwen 2006"
    )

    // ---- Lupton：平面设计原则 ----
    val hierarchy = TheoryRule(
        "L-HIER", "Lupton", "hierarchy", "TypeScale (4 sizes, 2 weights)",
        "层级靠字号+字重+墨色；一屏最多 4 级字号、2 种字重。",
        "Lupton 2010, Thinking with Type"
    )
    val grid = TheoryRule(
        "L-GRID", "Lupton", "grid", "Space (4/8/12/16/24/32/48)",
        "所有间距落在 4dp 栅格；页面边距 16/32。",
        "Lupton 2010; Carbon 2x; Polaris"
    )
    val rhythm = TheoryRule(
        "L-RHYTHM", "Lupton", "rhythm-balance", "Space + list rows",
        "重复使用同一组间距步进，形成节奏；不每屏发明新间距。",
        "Lupton 2010"
    )
    val scale = TheoryRule(
        "L-SCALE", "Lupton", "scale", "22/12 = 1.83",
        "标题与元信息保持约 1.8–2.0 倍尺度差，保证远读层级。",
        "Lupton 2010"
    )
    val modularity = TheoryRule(
        "L-MOD", "Lupton", "modularity", "component tokens + components",
        "用可重复组件构建复杂结构；屏幕不重造按钮/卡片。",
        "Lupton 2010"
    )
    val transparency = TheoryRule(
        "L-TRANS", "Lupton", "transparency", "scrim + tonal surfaces",
        "透明度只用于遮罩/叠加层；正文不透明，避免语义漂移。",
        "Lupton 2010"
    )

    val luptonFraming = TheoryRule(
        "L-FRAME", "Lupton", "framing", "Space.section + card boundary",
        "边界只表达范畴：卡片切对象，留白切组，分割线切行；三种不同时用。",
        "Lupton 2010"
    )
    val luptonFigureGround = TheoryRule(
        "L-FG", "Lupton", "figure-ground", "Palette.surface ladder",
        "图底作为构图策略：先定主体，再压背景；背景不抢正文对比。",
        "Lupton 2010"
    )

    val timeMotion = TheoryRule(
        "L-TIME", "Lupton", "time-motion", "Motion 150/250/300",
        "动效只表达状态变化与因果，150/250/300ms；不用装饰性弹跳。",
        "Lupton 2010; M3 motion"
    )



    // ---- 视觉文化 / 视觉修辞 ----
    val cjkTypography = TheoryRule(
        "C-CN", "Visual Culture", "cjk-typography", "NfType lineBreak/tracking",
        "中文 tracking=0、行距 1.5–1.75、行首行尾禁则；不套拉丁字距。",
        "W3C clreq; Lupton 2010"
    )
    val rtlMirror = TheoryRule(
        "C-RTL", "Visual Culture", "rtl-mirror", "Layout roles, not left/right",
        "信息角色替代绝对左右；RTL 时镜像方向，不镜像语义。",
        "Kress & van Leeuwen 2006"
    )
    val colorMeaning = TheoryRule(
        "C-SEM", "Visual Culture", "color-meaning", "status + text + shape",
        "颜色含义因文化而异；状态必须配文字/形状，不能只靠色。",
        "WCAG 1.4.1"
    )
    val ethos = TheoryRule(
        "R-ETHOS", "Visual Rhetoric", "ethos", "hash/time/source",
        "可信来自可核对证据：哈希、时间、来源，不来自权威口吻。",
        "Aristotle, Rhetoric"
    )
    val pathos = TheoryRule(
        "R-PATHOS", "Visual Rhetoric", "pathos", "no urgency/fear",
        "不用倒计时/恐吓/红色紧迫感操纵；情绪让位于任务。",
        "Aristotle, Rhetoric"
    )
    val logos = TheoryRule(
        "R-LOGOS", "Visual Rhetoric", "logos", "gates + structure",
        "论证靠结构、门禁、数字；每屏可回答“为什么这样”。",
        "Aristotle, Rhetoric"
    )

    // ---- 补充：认知/交互/信息设计 ----
    val fitts = TheoryRule("X-FITTS", "Fitts", "fitts-law", "Sizes.touchTarget + button",
        "目标越大越近越易点；主操作靠拇指区，触控 ≥48dp。", "Fitts 1954")
    val hick = TheoryRule("X-HICK", "Hick", "hick-law", "one primary + <=5 nav",
        "选择越多决策越慢；一屏一个主操作，导航 ≤5。", "Hick 1952; Hyman 1953")
    val miller = TheoryRule("X-MILLER", "Miller", "chunking", "4-level type + groups",
        "以 4 级层级和分组块降低记忆负担；不堆 7 个以上同级项。", "Miller 1956")
    val sweller = TheoryRule("X-SWELLER", "Cognitive Load", "extraneous-load", "one task per screen",
        "去掉与任务无关的装饰/说明；必要说明放帮助层。", "Sweller 1988")
    val doherty = TheoryRule("X-DOHERTY", "Doherty", "feedback-threshold", "Motion.fast + progress",
        "操作反馈 <400ms；长任务必须有进度/骨架。", "Doherty & Keller 1982")
    val jakob = TheoryRule("X-JAKOB", "Jakob", "consistency", "tokens + fixed nav",
        "沿用用户已会的模式；不创新导航/手势。", "Nielsen 2000")
    val peakEnd = TheoryRule("X-PEAK", "Peak-End", "peak-end", "export receipt",
        "结束体验决定记忆：导出成功必须有可核对回执。", "Kahneman 1993")
    val dataInk = TheoryRule("X-DATAINK", "Tufte", "data-ink", "hash/status rows",
        "证据区提高数据墨水比；去掉无信息装饰。", "Tufte 1983")

    // ---- Morville / HEART / Garrett / EDF：体验层 ----
    val useful = TheoryRule("M-USE", "Morville", "useful", "task model",
        "每个屏只服务一个用户任务；无任务内容不进首屏。", "Morville 2004")
    val usable = TheoryRule("M-USA", "Morville", "usable", "Sizes.touchTarget + error blocks",
        "触控 48dp；错误有码/人话/修复三步。", "Morville 2004")
    val desirable = TheoryRule("M-DES", "Morville", "desirable", "brand + motion",
        "品牌只通过一个强调色与克制动效表达，不牺牲可读性。", "Morville 2004")
    val findable = TheoryRule("M-FIND", "Morville", "findable", "search + navigation",
        "搜索可命中正文；导航固定五目的地以内。", "Morville 2004")
    val accessible = TheoryRule("M-ACC", "Morville", "accessible", "WCAG pairs + 200%",
        "对比/缩放/触控/读屏四类证据，缺一不算通过。", "Morville 2004; WCAG 2.2")
    val credible = TheoryRule("M-CRED", "Morville", "credible", "mono hash + timestamps",
        "证据可核对：哈希等宽分组、时间双格式、来源可回指。", "Morville 2004")
    val valuable = TheoryRule("M-VAL", "Morville", "valuable", "outcome metrics",
        "价值以任务完成与返工减少衡量，不以曝光量衡量。", "Morville 2004")

    val happiness = TheoryRule("H-HAP", "HEART", "happiness", "local feedback",
        "愉悦感来自可预期的反馈，不来自装饰。", "Rodden et al. 2010")
    val engagement = TheoryRule("H-ENG", "HEART", "engagement", "session tasks",
        "参与度看完成的有效任务数，不看停留时长。", "Rodden et al. 2010")
    val adoption = TheoryRule("H-ADO", "HEART", "adoption", "first-run → first export",
        "接受度看首次成功导出所需步骤。", "Rodden et al. 2010")
    val retention = TheoryRule("H-RET", "HEART", "retention", "local-only, no telemetry",
        "留存暂不埋点；以本地诊断/自愿反馈替代，不偷偷上报。", "Rodden et al. 2010")
    val taskSuccess = TheoryRule("H-TASK", "HEART", "task-success", "flow gates",
        "任务成功以 L1/导出通过为准；失败必须可恢复。", "Rodden et al. 2010")

    val strategy = TheoryRule("GAR-S", "Garrett", "strategy", "product scope",
        "本地优先、无网络权限是战略约束，不是实现细节。", "Garrett 2011")
    val scope = TheoryRule("GAR-SC", "Garrett", "scope", "feature set",
        "导入/切片/装配/导出四段范围，超出不进 0.2.0。", "Garrett 2011")
    val structure = TheoryRule("GAR-ST", "Garrett", "structure", "ShellState",
        "五目的地 + 单层详情栈；返回语义可预测。", "Garrett 2011")
    val skeleton = TheoryRule("GAR-SK", "Garrett", "skeleton", "Layout + Sizes",
        "骨架层用 64 顶栏/48 触控/16 边距固定。", "Garrett 2011")
    val surface = TheoryRule("GAR-SF", "Garrett", "surface", "tokens + theme",
        "表现层只消费令牌，不直接写色值/字号。", "Garrett 2011")

    val rules: List<TheoryRule> = listOf(
        proximity, similarity, continuity, closure, figureGround, commonFate,
        position, size, shape, value, hue, orientation, texture,
        informationValue, salience, framing,
        hierarchy, grid, rhythm, scale, modularity, transparency, luptonFraming, luptonFigureGround, timeMotion,
        useful, usable, desirable, findable, accessible, credible, valuable,
        cjkTypography, rtlMirror, colorMeaning, ethos, pathos, logos,
        fitts, hick, miller, sweller, doherty, jakob, peakEnd, dataInk,
        happiness, engagement, adoption, retention, taskSuccess,
        strategy, scope, structure, skeleton, surface
    )

    /** 必须有规则覆盖的构造名；测试防止“理论表越写越少”。 */
    val requiredConstructs: Set<String> = setOf(
        "proximity", "similarity", "continuity", "closure", "figure-ground", "common-fate",
        "position", "size", "shape", "value", "hue", "orientation", "texture",
        "information-value", "salience", "framing",
        "hierarchy", "grid", "rhythm-balance", "scale", "modularity", "transparency", "time-motion",
        "useful", "usable", "desirable", "findable", "accessible", "credible", "valuable",
        "cjk-typography", "rtl-mirror", "color-meaning", "ethos", "pathos", "logos",
        "fitts-law", "hick-law", "chunking", "extraneous-load", "feedback-threshold", "consistency", "peak-end", "data-ink",
        "happiness", "engagement", "adoption", "retention", "task-success",
        "strategy", "scope", "structure", "skeleton", "surface"
    )

    /**
     * 体验指标：先定义口径，再谈分数。instrumented=false 的项不得写成已测。
     */
    val metrics: List<QualityMetric> = listOf(
        QualityMetric("HEART-TASK", "Task success", "首次导出是否一次通过 L1？", "L1/导出回执", "≥90%", false),
        QualityMetric("HEART-TIME", "Time on task", "从导入到首个可交付草稿多久？", "本地步骤时间戳", "<5 min", false),
        QualityMetric("HEART-ERR", "Error recovery", "错误后能否在 1 屏内修复？", "错误卡 CTA", "100% 有 CTA", true),
        QualityMetric("MORVILLE-ACC", "Accessibility", "200% 缩放是否截断？", "截图矩阵", "0 截断", false),
        QualityMetric("MORVILLE-CRED", "Credibility", "证据是否可核对？", "哈希/时间/来源", "100% 可回指", true),
        QualityMetric("GARRETT-SF", "Surface discipline", "屏幕是否直接写色值/字号？", "design_lint", "0 违规", false)
    )
}
