package dev.ninfenz.mobile.core

/** 错误码浏览器过滤：code/message/fix 任一包含查询（大小写不敏感）。 */
object ErrorCodeFilter {
    fun apply(entries: List<ErrorCodeEntry>, query: String): List<ErrorCodeEntry> {
        val q = query.trim().lowercase()
        if (q.isEmpty()) return entries
        return entries.filter {
            it.code.lowercase().contains(q) ||
                it.message.lowercase().contains(q) ||
                it.fix.lowercase().contains(q)
        }
    }
}
