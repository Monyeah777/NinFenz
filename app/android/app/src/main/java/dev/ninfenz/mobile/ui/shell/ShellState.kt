package dev.ninfenz.mobile.ui.shell

enum class TopDestination(val label: String) {
    LIBRARY("库"),
    CREATE("创作"),
    DELIVER("交付"),
    ME("我的")
}

sealed interface Detail {
    data object Import : Detail
    data object Search : Detail
    data object NewProject : Detail
    data object Settings : Detail
    data object Protocol : Detail
    data object Graph : Detail
    data object Assembly : Detail
    data object PackUpdate : Detail
    data object Ccos : Detail
    data class Project(val id: String) : Detail
    data class Pack(val id: String, val version: String) : Detail
}

/** 四目的地 + 单层详情栈（W1）。纯数据，可单测；后续可替换为 Navigation Compose。 */
data class ShellState(
    val destination: TopDestination = TopDestination.LIBRARY,
    val detail: Detail? = null
) {
    fun select(destination: TopDestination): ShellState = copy(destination = destination, detail = null)

    fun open(detail: Detail): ShellState = copy(detail = detail)

    /** null = 已在根，交给系统返回（退出/预测返回）。 */
    fun back(): ShellState? = if (detail != null) copy(detail = null) else null
}
