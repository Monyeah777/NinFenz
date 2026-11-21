package dev.ninfenz.mobile.model

/** nf-doc 合并：不静默覆盖；同名章节保留双方并登记冲突，重复块按文本去重。 */
object NfDocMerger {
    data class Conflict(val title: String, val reason: String)
    data class Result(val doc: NfDoc, val conflicts: List<Conflict>)

    fun merge(left: NfDoc, right: NfDoc, title: String): Result {
        val leftSections = left.blocks.filter { it.type == "section" }.associateBy { it.title ?: it.text }
        val rightSections = right.blocks.filter { it.type == "section" }.associateBy { it.title ?: it.text }
        val conflicts = (leftSections.keys intersect rightSections.keys).map { key ->
            val a = leftSections.getValue(key)
            val b = rightSections.getValue(key)
            if (a.text != b.text) Conflict(key, "同名章节内容不同，已保留双方") else Conflict(key, "同名章节，已保留双方")
        }
        val seen = mutableSetOf<String>()
        val blocks = mutableListOf<NfDocBlock>()
        (left.blocks + right.blocks).forEach { block ->
            val key = block.type + "\u0000" + block.text
            if (seen.add(key)) blocks.add(block)
        }
        val doc = NfDoc(
            title = title.ifBlank { "合并文档" },
            sources = (left.sources + right.sources).distinct(),
            blocks = blocks.mapIndexed { index, block -> block.copy(id = "b" + (index + 1)) }
        )
        return Result(doc, conflicts)
    }
}
