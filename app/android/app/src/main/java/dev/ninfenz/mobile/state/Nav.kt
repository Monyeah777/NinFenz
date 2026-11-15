package dev.ninfenz.mobile.state

/** 屏幕枚举：与任务书 8 个屏幕一一对应。 */
enum class Screen(val title: String) {
    HOME("Home"),
    IMPORT("Import"),
    PROTOCOL("Protocol"),
    GRAPH("Graph"),
    ASSEMBLY("Assembly"),
    PACK_UPDATE("PackUpdate"),
    CCOS("Ccos"),
    SETTINGS("Settings")
}

/**
 * 纯导航栈（可单测）：返回键 pop 到根为止；push 去重相邻重复。
 * UI 层用 remember + mutableStateOf 持有，BackHandler 调 pop。
 */
data class NavState(val stack: List<Screen> = listOf(Screen.HOME)) {

    val current: Screen get() = stack.last()

    val canPop: Boolean get() = stack.size > 1

    fun push(screen: Screen): NavState =
        if (screen == current) this else copy(stack = stack + screen)

    fun pop(): NavState = if (!canPop) this else copy(stack = stack.dropLast(1))

    fun reset(screen: Screen): NavState = copy(stack = listOf(screen))
}
