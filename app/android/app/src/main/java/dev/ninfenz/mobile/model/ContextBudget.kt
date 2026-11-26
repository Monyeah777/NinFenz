package dev.ninfenz.mobile.model

/** AI 上下文预算：按字符/4 估算 token，先节后来源，超预算时显式截断。 */
data class ContextChunk(
    val id: String,
    val kind: String,
    val text: String,
    val tokens: Int,
    val truncated: Boolean = false
)

data class ContextPack(
    val chunks: List<ContextChunk>,
    val budgetTokens: Int,
    val usedTokens: Int,
    val trimmed: Boolean,
    val notes: List<String>
)

object ContextBudget {
    fun estimateTokens(text: String): Int = ((text.length + 3) / 4).coerceAtLeast(if (text.isEmpty()) 0 else 1)

    fun pack(
        sections: List<Pair<String, String>>,
        sources: List<String> = emptyList(),
        budgetTokens: Int
    ): ContextPack {
        val budget = budgetTokens.coerceAtLeast(0)
        val chunks = mutableListOf<ContextChunk>()
        var used = 0
        var trimmed = false
        val notes = mutableListOf<String>()

        fun add(id: String, kind: String, text: String) {
            val full = estimateTokens(text)
            if (used + full <= budget) {
                chunks += ContextChunk(id, kind, text, full)
                used += full
                return
            }
            val remaining = (budget - used).coerceAtLeast(0)
            if (remaining > 0) {
                val prefix = text.take(remaining * 4)
                val tokens = estimateTokens(prefix)
                chunks += ContextChunk(id, kind, prefix, tokens, truncated = true)
                used += tokens
            }
            trimmed = true
        }

        sections.forEach { (id, title) -> add(id, "section", id + ": " + title) }
        sources.forEachIndexed { index, text -> add("src-" + (index + 1), "source", text) }
        if (trimmed) notes += "上下文超出预算，已截断"
        if (budget == 0) notes += "预算为 0，未装入上下文"
        return ContextPack(chunks, budget, used, trimmed, notes)
    }
}
