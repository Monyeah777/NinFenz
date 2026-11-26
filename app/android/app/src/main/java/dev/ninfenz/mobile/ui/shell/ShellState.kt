package dev.ninfenz.mobile.ui.shell

enum class TopDestination(val labelRes: Int) {
    LIBRARY(dev.ninfenz.mobile.R.string.nav_library),
    FLOW(dev.ninfenz.mobile.R.string.nav_flow),
    CREATE(dev.ninfenz.mobile.R.string.nav_create),
    DELIVER(dev.ninfenz.mobile.R.string.nav_deliver),
    ME(dev.ninfenz.mobile.R.string.nav_me)
}

sealed interface Detail {
    data object Import : Detail
    data object Inbox : Detail
    data object Search : Detail
    data object NewProject : Detail
    data object Settings : Detail
    data object DesignSystem : Detail
    data object DecisionLog : Detail
    data object ErrorCodes : Detail
    data object Extensions : Detail
    data object Protocol : Detail
    data object Graph : Detail
    data object Assembly : Detail
    data object PackUpdate : Detail
    data object PackCenter : Detail
    data object Ccos : Detail
    data object NfDocMerge : Detail
    data class Patch(val projectId: String? = null) : Detail
    data class Project(val id: String) : Detail
    data class Author(val id: String) : Detail
    data class Delivery(val id: String) : Detail
    data class Review(val id: String) : Detail
    data class PackBuilder(val id: String) : Detail
    data class Flow(val id: String) : Detail
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
