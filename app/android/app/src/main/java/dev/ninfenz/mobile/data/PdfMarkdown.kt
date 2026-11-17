package dev.ninfenz.mobile.data

/** PDF 基础文本预处理：去 Markdown 标记、标题符号、链接/图片语法与代码围栏。 */
object PdfMarkdown {
    data class Block(
        val text: String,
        val level: Int = 0,
        val bullet: Boolean = false,
        val code: Boolean = false,
        val table: Boolean = false
    )

    fun blocks(markdown: String): List<Block> {
        val out = mutableListOf<Block>()
        var inCode = false
        for (raw in markdown.replace("\r\n", "\n").split('\n')) {
            val trimmed = raw.trim()
            if (trimmed.startsWith("\u0060\u0060\u0060") || trimmed.startsWith("~~~")) {
                inCode = !inCode
                continue
            }
            if (inCode) {
                out.add(Block(raw, code = true))
                continue
            }
            if (trimmed.isEmpty()) continue
            if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
                val cells = trimmed.trim('|').split('|').map { inline(it.trim()) }
                if (cells.all { Regex("^:?-{3,}:?$").matches(it) }) continue
                out.add(Block(cells.joinToString("  "), table = true))
                continue
            }
            val hashes = trimmed.takeWhile { it == '#' }.length
            if (hashes in 1..6) {
                out.add(Block(inline(trimmed.substring(hashes).trim()), level = hashes))
                continue
            }
            if (trimmed.startsWith("- ") || trimmed.startsWith("* ") || trimmed.startsWith("+ ")) {
                out.add(Block(inline(trimmed.substring(2).trim()), bullet = true))
                continue
            }
            out.add(Block(inline(trimmed)))
        }
        return out
    }

    fun lines(markdown: String): List<String> = blocks(markdown).map {
        (if (it.bullet) "• " else "") + it.text
    }

    fun inline(s: String): String {
        var text = s
        text = Regex("!\\[([^\\]]*)\\]\\([^)]*\\)").replace(text, "$1")
        text = Regex("\\[([^\\]]*)\\]\\([^)]*\\)").replace(text, "$1")
        text = text.replace("**", "").replace("__", "").replace("~~", "").replace("\u0060", "")
        text = text.replace("*", "")
        return text.trim()
    }
}
