package dev.ninfenz.mobile.model

/** nf-doc 合并：不静默覆盖；同名章节保留双方并登记冲突，重复块按文本去重。 */
object NfDocMerger {
    enum class Keep { LEFT, RIGHT, BOTH }
    data class Conflict(
        val title: String,
        val reason: String,
        val leftSources: List<String> = emptyList(),
        val rightSources: List<String> = emptyList()
    )
    data class Result(val doc: NfDoc, val conflicts: List<Conflict>)

    fun merge(left: NfDoc, right: NfDoc, title: String): Result {
        val leftSections = left.blocks.filter { it.type == "section" }.associateBy { it.title ?: it.text }
        val rightSections = right.blocks.filter { it.type == "section" }.associateBy { it.title ?: it.text }
        val conflicts = (leftSections.keys intersect rightSections.keys).map { key ->
            val a = leftSections.getValue(key)
            val b = rightSections.getValue(key)
            if (a.text != b.text) {
                Conflict(key, "同名章节内容不同，已保留双方", left.sources, right.sources)
            } else {
                Conflict(key, "同名章节，已保留双方", left.sources, right.sources)
            }
        }
        val seen = mutableSetOf<String>()
        val blocks = mutableListOf<NfDocBlock>()
        (left.blocks + right.blocks).forEach { block ->
            val key = if (block.type == "section") {
                block.type + "\u0000" + block.text + "\u0000" + (block.source ?: "")
            } else {
                block.type + "\u0000" + block.text
            }
            if (seen.add(key)) blocks.add(block)
        }
        val doc = NfDoc(
            title = title.ifBlank { "合并文档" },
            sources = (left.sources + right.sources).distinct(),
            blocks = blocks.mapIndexed { index, block -> block.copy(id = "b" + (index + 1)) }
        )
        return Result(doc, conflicts)
    }

    /** 三方合并：base/local/remote；同块双改进冲突，单边改动直接取。 */
    private fun sameContent(a: NfDocBlock?, b: NfDocBlock?): Boolean =
        if (a == null || b == null) a == null && b == null
        else a.type == b.type && a.text == b.text && a.title == b.title && a.slot == b.slot

    fun merge3(base: NfDoc, left: NfDoc, right: NfDoc, title: String): Result {
        val baseMap = base.blocks.associateBy { it.id }
        val leftMap = left.blocks.associateBy { it.id }
        val rightMap = right.blocks.associateBy { it.id }
        val ids = LinkedHashSet<String>()
        base.blocks.forEach { ids.add(it.id) }
        left.blocks.forEach { ids.add(it.id) }
        right.blocks.forEach { ids.add(it.id) }

        val conflicts = mutableListOf<Conflict>()
        val chosen = linkedMapOf<String, NfDocBlock>()
        for (id in ids) {
            val b = baseMap[id]
            val l = leftMap[id]
            val r = rightMap[id]
            when {
                sameContent(l, r) -> l?.let { chosen[id] = it }
                sameContent(l, b) -> r?.let { chosen[id] = it }
                sameContent(r, b) -> l?.let { chosen[id] = it }
                else -> {
                    val fallback = l ?: r ?: b
                    if (fallback != null) {
                        chosen[id] = fallback
                        conflicts += Conflict(
                            title = fallback.title ?: fallback.text.take(40),
                            reason = if (b == null) "双方新增不同内容" else "同块双改",
                            leftSources = l?.source?.let { listOf(it) } ?: emptyList(),
                            rightSources = r?.source?.let { listOf(it) } ?: emptyList()
                        )
                    }
                }
            }
        }
        val ordered = linkedSetOf<String>()
        base.blocks.forEach { ordered.add(it.id) }
        left.blocks.forEach { ordered.add(it.id) }
        right.blocks.forEach { ordered.add(it.id) }
        val blocks = ordered.mapNotNull { chosen[it] }
            .mapIndexed { index, block -> block.copy(id = "b" + (index + 1)) }
        val doc = NfDoc(
            title = title.ifBlank { "合并文档" },
            sources = (base.sources + left.sources + right.sources).distinct(),
            blocks = blocks
        )
        return Result(doc, conflicts)
    }

    /** 逐项消解：只移除冲突章节及其后续块，不碰其他章节。 */
    fun resolve(doc: NfDoc, conflict: Conflict, keep: Keep): NfDoc {
        if (keep == Keep.BOTH) return doc
        val remove = if (keep == Keep.LEFT) conflict.rightSources.toSet() else conflict.leftSources.toSet()
        if (remove.isEmpty()) return doc
        val kept = mutableListOf<NfDocBlock>()
        var dropping = false
        doc.blocks.forEach { block ->
            if (block.type == "section") {
                dropping = block.title == conflict.title && block.source in remove
            }
            if (!dropping) kept.add(block)
        }
        return doc.copy(blocks = kept.mapIndexed { index, block -> block.copy(id = "b" + (index + 1)) })
    }
}
