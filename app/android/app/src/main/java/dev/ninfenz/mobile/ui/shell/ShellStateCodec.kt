package dev.ninfenz.mobile.ui.shell

/** ShellState 的进程死亡恢复编码：纯字符串列表，未知 detail 回退到根。 */
object ShellStateCodec {
    fun encode(state: ShellState): List<String> {
        val d = state.detail
        val type = when (d) {
            null -> "none"
            Detail.Import -> "Import"
            Detail.Inbox -> "Inbox"
            Detail.Search -> "Search"
            Detail.NewProject -> "NewProject"
            Detail.Settings -> "Settings"
            Detail.DesignSystem -> "DesignSystem"
            Detail.DecisionLog -> "DecisionLog"
            Detail.ErrorCodes -> "ErrorCodes"
            Detail.Extensions -> "Extensions"
            Detail.Protocol -> "Protocol"
            Detail.Graph -> "Graph"
            Detail.Assembly -> "Assembly"
            Detail.PackUpdate -> "PackUpdate"
            Detail.PackCenter -> "PackCenter"
            Detail.Ccos -> "Ccos"
            Detail.NfDocMerge -> "NfDocMerge"
            is Detail.Patch -> "Patch"
            is Detail.Project -> "Project"
            is Detail.Author -> "Author"
            is Detail.Delivery -> "Delivery"
            is Detail.Review -> "Review"
            is Detail.PackBuilder -> "PackBuilder"
            is Detail.Flow -> "Flow"
            is Detail.Pack -> "Pack"
        }
        val arg1 = when (d) {
            is Detail.Project -> d.id
            is Detail.Author -> d.id
            is Detail.Delivery -> d.id
            is Detail.Review -> d.id
            is Detail.PackBuilder -> d.id
            is Detail.Flow -> d.id
            is Detail.Pack -> d.id
            is Detail.Patch -> d.projectId ?: ""
            else -> ""
        }
        val arg2 = when (d) {
            is Detail.Pack -> d.version
            else -> ""
        }
        return listOf(state.destination.name, type, arg1, arg2)
    }

    fun decode(values: List<String>): ShellState {
        val destination = values.getOrNull(0)?.let { name ->
            TopDestination.entries.firstOrNull { it.name == name }
        } ?: TopDestination.LIBRARY
        val detail = when (values.getOrNull(1)) {
            "Import" -> Detail.Import
            "Inbox" -> Detail.Inbox
            "Search" -> Detail.Search
            "NewProject" -> Detail.NewProject
            "Settings" -> Detail.Settings
            "DesignSystem" -> Detail.DesignSystem
            "DecisionLog" -> Detail.DecisionLog
            "ErrorCodes" -> Detail.ErrorCodes
            "Extensions" -> Detail.Extensions
            "Protocol" -> Detail.Protocol
            "Graph" -> Detail.Graph
            "Assembly" -> Detail.Assembly
            "PackUpdate" -> Detail.PackUpdate
            "PackCenter" -> Detail.PackCenter
            "Ccos" -> Detail.Ccos
            "NfDocMerge" -> Detail.NfDocMerge
            "Patch" -> Detail.Patch(values.getOrNull(2)?.takeIf { it.isNotBlank() })
            "Project" -> values.getOrNull(2)?.takeIf { it.isNotBlank() }?.let { Detail.Project(it) }
            "Author" -> values.getOrNull(2)?.takeIf { it.isNotBlank() }?.let { Detail.Author(it) }
            "Delivery" -> values.getOrNull(2)?.takeIf { it.isNotBlank() }?.let { Detail.Delivery(it) }
            "Review" -> values.getOrNull(2)?.takeIf { it.isNotBlank() }?.let { Detail.Review(it) }
            "PackBuilder" -> values.getOrNull(2)?.takeIf { it.isNotBlank() }?.let { Detail.PackBuilder(it) }
            "Flow" -> values.getOrNull(2)?.takeIf { it.isNotBlank() }?.let { Detail.Flow(it) }
            "Pack" -> {
                val id = values.getOrNull(2)?.takeIf { it.isNotBlank() }
                val version = values.getOrNull(3)?.takeIf { it.isNotBlank() }
                if (id != null && version != null) Detail.Pack(id, version) else null
            }
            else -> null
        }
        return ShellState(destination, detail)
    }
}
