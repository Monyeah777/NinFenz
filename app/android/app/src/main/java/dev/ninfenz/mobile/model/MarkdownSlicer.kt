package dev.ninfenz.mobile.model

/** 本地结构切片：标题开启章节，其余块归入当前章节；无标题时归入开篇。 */
data class MarkdownSlice(
    val heading: String?,
    val level: Int,
    val blocks: List<MarkdownBlock>
) {
    val charCount: Int get() = blocks.sumOf { it.text.length }
}

object MarkdownSlicer {
    fun slice(blocks: List<MarkdownBlock>): List<MarkdownSlice> {
        val out = mutableListOf<MarkdownSlice>()
        var heading: String? = null
        var level = 0
        var body = mutableListOf<MarkdownBlock>()

        fun flush() {
            if (heading != null || body.isNotEmpty()) {
                out.add(MarkdownSlice(heading, level, body.toList()))
            }
            body = mutableListOf()
        }

        for (block in blocks) {
            val first = block.text.lineSequence().firstOrNull().orEmpty()
            val match = Regex("^(#{1,6})\\s+(.+)$").find(first.trim())
            if (match != null && block.text.lineSequence().count() == 1) {
                flush()
                level = match.groupValues[1].length
                heading = match.groupValues[2].trim()
            } else {
                body.add(block)
            }
        }
        flush()
        return out
    }
}
