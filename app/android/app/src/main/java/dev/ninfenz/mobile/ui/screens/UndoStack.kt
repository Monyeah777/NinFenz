package dev.ninfenz.mobile.ui.screens

/** 有界撤销栈：长期编辑时避免历史无限膨胀；保留最近 limit 条。 */
object UndoStack {
    const val DEFAULT_LIMIT = 100

    fun <T> push(stack: List<T>, item: T, limit: Int = DEFAULT_LIMIT): List<T> {
        if (limit <= 0) return emptyList()
        val next = stack + item
        return if (next.size <= limit) next else next.subList(next.size - limit, next.size).toList()
    }
}
