package dev.ninfenz.mobile.model

/** 命令面板：按标题过滤，空查询返回全部；不做模糊拼写。 */
object CommandPalette {
    data class Item(val id: String, val title: String)

    fun filter(items: List<Item>, query: String): List<Item> {
        val q = query.trim().lowercase()
        if (q.isEmpty()) return items
        return items.filter { it.title.lowercase().contains(q) || it.id.lowercase().contains(q) }
    }
}
