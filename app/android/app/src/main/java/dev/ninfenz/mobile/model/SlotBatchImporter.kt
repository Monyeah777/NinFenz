package dev.ninfenz.mobile.model

/**
 * 多槽位批量导入：先用 --- 或空行做确定性分段，再逐段适配 Markdown/纯文本。
 * 不做语义猜测；槽位按 plan 顺序与段顺序一一对应。
 */
object SlotBatchImporter {
    data class Chunk(val text: String, val format: String)

    data class FillResult(
        val values: Map<String, String>,
        val filled: Int,
        val skipped: Int,
        val appended: Int,
        val dropped: Int
    )

    fun split(text: String): List<String> {
        val normalized = SlotTextAdapter.normalize(text)
        val stripped = SlotTextAdapter.stripFrontMatter(normalized)
        val separator = Regex("(?m)^\\s*---\\s*$")
        val parts = if (separator.containsMatchIn(stripped)) {
            stripped.split(separator)
        } else {
            stripped.split(Regex("\\n\\s*\\n"))
        }
        return parts.map { it.trim() }.filter { it.isNotEmpty() }
    }

    fun chunks(raw: String, fileName: String? = null): List<Chunk> =
        split(raw)
            .map { SlotTextAdapter.adapt(it, fileName) }
            .filter { it.adapted.isNotBlank() }
            .map { Chunk(it.adapted, it.format) }

    /**
     * onlyEmpty=true 只填空白槽；超出段丢弃。
     * onlyEmpty=false 有段的槽位覆盖；超出段追加到最后一个槽位。
     */
    fun apply(
        chunks: List<Chunk>,
        slots: List<String>,
        current: Map<String, String>,
        onlyEmpty: Boolean
    ): FillResult {
        if (slots.isEmpty()) return FillResult(current, 0, 0, 0, chunks.size)
        val updated = current.toMutableMap()
        val mapped = minOf(chunks.size, slots.size)
        var filled = 0
        var skipped = 0
        for (i in 0 until mapped) {
            val slot = slots[i]
            val old = updated[slot].orEmpty()
            if (onlyEmpty && old.isNotBlank()) {
                skipped++
            } else {
                updated[slot] = chunks[i].text
                filled++
            }
        }
        var appended = 0
        var dropped = 0
        if (chunks.size > slots.size) {
            val overflow = chunks.drop(slots.size).joinToString("\n\n") { it.text }
            if (onlyEmpty) {
                dropped = chunks.size - slots.size
            } else {
                val last = slots.last()
                val old = updated[last].orEmpty().trim()
                updated[last] = if (old.isBlank()) overflow else old + "\n\n" + overflow
                appended = chunks.size - slots.size
            }
        }
        return FillResult(updated, filled, skipped, appended, dropped)
    }
}
