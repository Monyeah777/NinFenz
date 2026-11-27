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
            if (isTableLine(trimmed)) {
                lastTableBlock = addTableLine(trimmed, out, lastTableBlock)
                continue
            }
            lastTableBlock = -1
            val classified = classifiedBlock(trimmed)
            if (classified != null) {
                out.add(classified)
                continue
            }
            out.add(blockOf(trimmed))
        }
        return out
    }

    private fun isTableLine(trimmed: String): Boolean =
        trimmed.startsWith("|") && trimmed.endsWith("|")

    private fun addTableLine(trimmed: String, out: MutableList<Block>, lastTableBlock: Int): Int {
        val cells = trimmed.trim('|').split('|').map { inline(it.trim()) }
        if (cells.all { Regex("^:?-{3,}:?$").matches(it) }) {
            if (lastTableBlock >= 0) out[lastTableBlock] = out[lastTableBlock].copy(tableHeader = true)
            return -1
        }
        out.add(Block(cells.joinToString("  "), table = true, cells = cells))
        return out.lastIndex
    }

    private fun classifiedBlock(trimmed: String): Block? {
        imageBlock(trimmed)?.let { return it }
        if (isRuleLine(trimmed)) return Block("", rule = true)
        if (trimmed.startsWith(">")) return blockOf(trimmed.removePrefix(">").trim(), quote = true)
        val hashes = trimmed.takeWhile { it == '#' }.length
        if (hashes in 1..6) return blockOf(trimmed.substring(hashes).trim(), level = hashes)
        if (trimmed.startsWith("- ") || trimmed.startsWith("* ") || trimmed.startsWith("+ ")) {
            return blockOf(trimmed.substring(2).trim(), bullet = true)
        }
        return null
    }

    private fun imageBlock(trimmed: String): Block? {
        val imageMatch = Regex("^!\\[([^\\]]*)\\]\\(data:image/[^;]+;base64,([^)]+)\\)$").find(trimmed) ?: return null
        val bytes = runCatching { java.util.Base64.getDecoder().decode(imageMatch.groupValues[2].trim()) }.getOrNull() ?: return null
        return Block(imageMatch.groupValues[1], image = bytes)
    }

    private fun isRuleLine(trimmed: String): Boolean =
        trimmed.length >= 3 && (trimmed.all { it == '-' } || trimmed.all { it == '*' } || trimmed.all { it == '_' })

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
        while (i < text.length) {
            val marked = markerAt(text, i)
            if (marked != null) {
                marked.span?.let { out.add(it) }
                i = marked.next
                continue
            }
            var j = i + 1
            while (j < text.length && !text.startsWith("**", j) && !text.startsWith("__", j) &&
                text[j] != '\u0060' && text[j] != '*' && text[j] != '_'
            ) j++
            out.add(Span(text.substring(i, j)))
            i = j
        }
        return out.ifEmpty { listOf(Span("")) }
    }

    private data class Marked(val span: Span?, val next: Int)

    private class Marker(
        val open: String,
        val close: String,
        val bold: Boolean = false,
        val italic: Boolean = false,
        val code: Boolean = false
    )

    private fun markerAt(text: String, i: Int): Marked? = when {
        text.startsWith("**", i) -> marked(text, i, Marker("**", "**", bold = true))
        text.startsWith("__", i) -> marked(text, i, Marker("__", "__", bold = true))
        text.startsWith("\u0060", i) -> marked(text, i, Marker("\u0060", "\u0060", code = true))
        text.startsWith("*", i) -> marked(text, i, Marker("*", "*", italic = true))
        text.startsWith("_", i) -> marked(text, i, Marker("_", "_", italic = true))
        else -> null
    }

    private fun marked(text: String, i: Int, marker: Marker): Marked? {
        if (!text.startsWith(marker.open, i)) return null
        val end = text.indexOf(marker.close, i + marker.open.length)
        if (end < 0) return null
        val inner = text.substring(i + marker.open.length, end)
        val span = if (inner.isNotEmpty()) Span(inner, bold = marker.bold, italic = marker.italic, code = marker.code) else null
        return Marked(span, end + marker.close.length)
    }

    fun inline(s: String): String = spanize(s).joinToString("") { it.text }.trim()
}
