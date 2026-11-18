package dev.ninfenz.mobile.model

/** 轻量 Markdown 块：按空行切分，代码围栏内的空行不切；用于块级预览编辑。 */
data class MarkdownBlock(val id: Int, val text: String)

object MarkdownBlocks {
    fun parse(markdown: String): List<MarkdownBlock> {
        if (markdown.isBlank()) return emptyList()
        val blocks = mutableListOf<String>()
        val current = StringBuilder()
        var inFence = false
        fun flush() {
            val text = current.toString().trim()
            if (text.isNotEmpty()) blocks.add(text)
            current.clear()
        }
        for (line in markdown.replace("\r\n", "\n").split("\n")) {
            if (line.trimStart().startsWith("```")) {
                if (inFence) {
                    current.appendLine(line)
                    flush()
                    inFence = false
                } else {
                    flush()
                    current.appendLine(line)
                    inFence = true
                }
            } else if (!inFence && line.isBlank()) {
                flush()
            } else {
                current.appendLine(line)
            }
        }
        if (inFence) flush() else flush()
        return blocks.mapIndexed { index, text -> MarkdownBlock(index, text) }
    }

    fun render(blocks: List<MarkdownBlock>): String =
        blocks.map { it.text.trim() }.filter { it.isNotEmpty() }.joinToString("\n\n")
}
