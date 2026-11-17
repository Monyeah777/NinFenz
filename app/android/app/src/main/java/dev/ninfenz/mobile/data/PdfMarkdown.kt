package dev.ninfenz.mobile.data

/** PDF 基础文本预处理：去 Markdown 标记、标题符号、链接/图片语法与代码围栏。 */
object PdfMarkdown {
    data class Span(
        val text: String,
        val bold: Boolean = false,
        val italic: Boolean = false,
        val code: Boolean = false
    )

    data class Block(
        val text: String,
        val level: Int = 0,
        val bullet: Boolean = false,
        val code: Boolean = false,
        val table: Boolean = false,
        val tableHeader: Boolean = false,
        val quote: Boolean = false,
        val rule: Boolean = false,
        val cells: List<String> = emptyList(),
        val spans: List<Span> = emptyList(),
        val image: ByteArray? = null
    )

    fun blocks(markdown: String): List<Block> {
        val out = mutableListOf<Block>()
        var inCode = false
        var lastTableBlock = -1
        for (raw in markdown.replace("\r\n", "\n").split('\n')) {
            val trimmed = raw.trim()
            if (trimmed.startsWith("\u0060\u0060\u0060") || trimmed.startsWith("~~~")) {
                inCode = !inCode
                continue
            }
            if (inCode) {
                out.add(Block(raw, code = true))
                lastTableBlock = -1
                continue
            }
            if (trimmed.isEmpty()) continue
            if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
                val cells = trimmed.trim('|').split('|').map { inline(it.trim()) }
                if (cells.all { Regex("^:?-{3,}:?$").matches(it) }) {
                    if (lastTableBlock >= 0) {
                        out[lastTableBlock] = out[lastTableBlock].copy(tableHeader = true)
                        lastTableBlock = -1
                    }
                    continue
                }
                out.add(Block(cells.joinToString("  "), table = true, cells = cells))
                lastTableBlock = out.lastIndex
                continue
            }
            lastTableBlock = -1
            val imageMatch = Regex("^!\\[([^\\]]*)\\]\\(data:image/[^;]+;base64,([^)]+)\\)$").find(trimmed)
            if (imageMatch != null) {
                val bytes = runCatching { java.util.Base64.getDecoder().decode(imageMatch.groupValues[2].trim()) }.getOrNull()
                if (bytes != null) {
                    out.add(Block(imageMatch.groupValues[1], image = bytes))
                    continue
                }
            }
            if (trimmed.length >= 3 && (trimmed.all { it == '-' } || trimmed.all { it == '*' } || trimmed.all { it == '_' })) {
                out.add(Block("", rule = true))
                continue
            }
            if (trimmed.startsWith(">")) {
                out.add(blockOf(trimmed.removePrefix(">").trim(), quote = true))
                continue
            }
            val hashes = trimmed.takeWhile { it == '#' }.length
            if (hashes in 1..6) {
                out.add(blockOf(trimmed.substring(hashes).trim(), level = hashes))
                continue
            }
            if (trimmed.startsWith("- ") || trimmed.startsWith("* ") || trimmed.startsWith("+ ")) {
                out.add(blockOf(trimmed.substring(2).trim(), bullet = true))
                continue
            }
            out.add(blockOf(trimmed))
        }
        return out
    }

    fun lines(markdown: String): List<String> = blocks(markdown).map {
        when {
            it.rule -> ""
            it.quote -> "│ " + it.text
            it.bullet -> "• " + it.text
            else -> it.text
        }
    }

    private fun blockOf(raw: String, level: Int = 0, bullet: Boolean = false, quote: Boolean = false): Block {
        val spans = spanize(raw)
        return Block(spans.joinToString("") { it.text }, level = level, bullet = bullet, quote = quote, spans = spans)
    }

    fun spanize(raw: String): List<Span> {
        var text = raw
        text = Regex("!\\[([^\\]]*)\\]\\([^)]*\\)").replace(text) { it.groupValues[1] }
        text = Regex("\\[([^\\]]*)\\]\\([^)]*\\)").replace(text) { it.groupValues[1] }
        text = text.replace("~~", "")
        val out = mutableListOf<Span>()
        var i = 0
        fun marker(open: String, close: String, bold: Boolean = false, italic: Boolean = false, code: Boolean = false): Boolean {
            if (!text.startsWith(open, i)) return false
            val end = text.indexOf(close, i + open.length)
            if (end < 0) return false
            val inner = text.substring(i + open.length, end)
            if (inner.isNotEmpty()) out.add(Span(inner, bold = bold, italic = italic, code = code))
            i = end + close.length
            return true
        }
        while (i < text.length) {
            when {
                marker("**", "**", bold = true) -> {}
                marker("__", "__", bold = true) -> {}
                marker("\u0060", "\u0060", code = true) -> {}
                marker("*", "*", italic = true) -> {}
                marker("_", "_", italic = true) -> {}
                else -> {
                    var j = i + 1
                    while (j < text.length && !text.startsWith("**", j) && !text.startsWith("__", j) &&
                        text[j] != '\u0060' && text[j] != '*' && text[j] != '_'
                    ) j++
                    out.add(Span(text.substring(i, j)))
                    i = j
                }
            }
        }
        return out.ifEmpty { listOf(Span("")) }
    }

    fun inline(s: String): String = spanize(s).joinToString("") { it.text }.trim()
}
