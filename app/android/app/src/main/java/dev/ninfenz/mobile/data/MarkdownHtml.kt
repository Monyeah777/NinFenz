package dev.ninfenz.mobile.data

/**
 * Markdown → HTML 块级渲染，HTML 导出与 EPUB 章节共用（D-002：消除两份逐行重复的实现）。
 * 两者差异只在图片策略：HTML 允许 http(s)/data 图；EPUB 只允许 data:image 内嵌。
 */
internal object MarkdownHtml {
    enum class ImagePolicy { REMOTE_AND_DATA, DATA_ONLY }

    fun esc(s: String): String = s
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")

    fun inline(s: String, policy: ImagePolicy): String {
        var text = esc(s)
        text = Regex("\u0060([^\u0060]+)\u0060").replace(text, "<code>$1</code>")
        text = Regex("\\*\\*([^*]+)\\*\\*").replace(text, "<strong>$1</strong>")
        text = Regex("\\*([^*]+)\\*").replace(text, "<em>$1</em>")
        text = Regex("~~([^~]+)~~").replace(text, "<del>$1</del>")
        text = Regex("!\\[([^\\]]*)\\]\\(([^)]+)\\)").replace(text) { match ->
            val src = match.groupValues[2]
            if (imageAllowed(src, policy)) {
                "<img src=\"" + src + "\" alt=\"" + match.groupValues[1] + "\"/>"
            } else {
                match.value
            }
        }
        text = Regex("\\[([^\\]]+)\\]\\(([^)]+)\\)").replace(text) { match ->
            val href = match.groupValues[2]
            if (href.startsWith("http://") || href.startsWith("https://") || href.startsWith("mailto:") || href.startsWith("#")) {
                "<a href=\"" + href + "\">" + match.groupValues[1] + "</a>"
            } else {
                match.value
            }
        }
        return text
    }

    private fun imageAllowed(src: String, policy: ImagePolicy): Boolean =
        if (policy == ImagePolicy.DATA_ONLY) {
            src.startsWith("data:image/")
        } else {
            src.startsWith("http://") || src.startsWith("https://") || src.startsWith("data:image/")
        }

    fun body(markdown: String, policy: ImagePolicy): String {
        val writer = MarkdownHtmlWriter(policy)
        markdown.replace("\r\n", "\n").split('\n').forEach { writer.line(it) }
        return writer.finish()
    }
}

private class MarkdownHtmlWriter(private val policy: MarkdownHtml.ImagePolicy) {
    private val out = StringBuilder()
    private var inCode = false
    private var inList = false
    private var inQuote = false
    private var inOrdered = false
    private var codeLang = ""
    private val code = StringBuilder()
    private val table = mutableListOf<List<String>>()
    private var tableAlign = emptyList<String>()

    fun line(raw: String) {
        if (raw.trimStart().startsWith("\u0060\u0060\u0060")) {
            handleFence(raw)
            return
        }
        if (inCode) {
            code.append(raw).append('\n')
            return
        }
        if (raw.isBlank()) {
            closeLists()
            flushTable()
            closeQuote()
            return
        }
        val trimmed = raw.trim()
        if (trimmed.startsWith("> ")) {
            handleQuote(trimmed)
            return
        }
        if (handleOrdered(trimmed)) return
        if (handleTable(trimmed)) return
        if (handleRule(trimmed)) return
        if (handleHeading(raw)) return
        if (handleBullet(raw)) return
        closeLists()
        flushTable()
        closeQuote()
        out.append("<p>").append(MarkdownHtml.inline(raw, policy)).append("</p>\n")
    }

    fun finish(): String {
        flushTable()
        closeQuote()
        closeLists()
        if (inCode && code.isNotEmpty()) out.append("<pre><code>").append(MarkdownHtml.esc(code.toString().trimEnd())).append("</code></pre>\n")
        return out.toString()
    }

    private fun closeQuote() {
        if (inQuote) { out.append("</blockquote>"); inQuote = false }
    }

    private fun closeLists() {
        if (inList) { out.append("</ul>\n"); inList = false }
        if (inOrdered) { out.append("</ol>\n"); inOrdered = false }
    }

    private fun flushTable() {
        if (table.isEmpty()) return
        out.append("<table>")
        table.forEachIndexed { index, cells ->
            val tag = if (index == 0) "th" else "td"
            if (index == 0) out.append("<thead>")
            if (index == 1) out.append("<tbody>")
            out.append("<tr>")
            cells.forEachIndexed { i, cell ->
                val align = tableAlign.getOrNull(i).orEmpty()
                val style = if (align.isBlank()) "" else " style=\"text-align:" + align + "\""
                out.append("<").append(tag).append(style).append(">").append(MarkdownHtml.inline(cell, policy)).append("</").append(tag).append(">")
            }
            out.append("</tr>")
            if (index == 0) out.append("</thead>")
        }
        if (table.size > 1) out.append("</tbody>")
        out.append("</table>")
        table.clear()
        tableAlign = emptyList()
    }

    private fun handleFence(raw: String) {
        if (inCode) {
            val cls = if (codeLang.isNotBlank()) " class=\"language-" + codeLang + "\"" else ""
            out.append("<pre><code").append(cls).append(">").append(MarkdownHtml.esc(code.toString().trimEnd())).append("</code></pre>\n")
            code.clear()
            codeLang = ""
        } else {
            codeLang = raw.trimStart().removePrefix("\u0060\u0060\u0060").trim().takeWhile { it.isLetterOrDigit() || it == '_' || it == '-' }
        }
        inCode = !inCode
    }

    private fun handleQuote(trimmed: String) {
        flushTable()
        closeLists()
        if (!inQuote) { out.append("<blockquote>"); inQuote = true }
        out.append("<p>").append(MarkdownHtml.inline(trimmed.removePrefix("> "), policy)).append("</p>")
    }

    private fun handleOrdered(trimmed: String): Boolean {
        val ordered = Regex("^\\s*\\d+\\.\\s+(.+)$").find(trimmed) ?: return false
        flushTable()
        closeQuote()
        if (inList) { out.append("</ul>\n"); inList = false }
        if (!inOrdered) { out.append("<ol>"); inOrdered = true }
        out.append("<li>").append(MarkdownHtml.inline(ordered.groupValues[1], policy)).append("</li>")
        return true
    }

    private fun handleTable(trimmed: String): Boolean {
        if (!(trimmed.startsWith("|") && trimmed.endsWith("|"))) return false
        closeQuote()
        closeLists()
        val cells = trimmed.trim('|').split('|').map { it.trim() }
        val separator = cells.isNotEmpty() && cells.all { Regex("^:?-{2,}:?$").matches(it) }
        if (separator) {
            tableAlign = cells.map {
                when {
                    it.startsWith(":") && it.endsWith(":") -> "center"
                    it.startsWith(":") -> "left"
                    it.endsWith(":") -> "right"
                    else -> ""
                }
            }
        } else {
            table.add(cells)
        }
        return true
    }

    private fun handleRule(trimmed: String): Boolean {
        if (!Regex("^-{3,}$").matches(trimmed)) return false
        flushTable()
        closeQuote()
        closeLists()
        out.append("<hr/>")
        return true
    }

    private fun handleHeading(line: String): Boolean {
        val heading = Regex("^(#{1,6})\\s+(.+)$").find(line) ?: return false
        flushTable()
        closeQuote()
        closeLists()
        val level = heading.groupValues[1].length
        out.append("<h").append(level).append(">").append(MarkdownHtml.inline(heading.groupValues[2], policy)).append("</h").append(level).append(">\n")
        return true
    }

    private fun handleBullet(line: String): Boolean {
        if (!line.trimStart().startsWith("- ")) return false
        flushTable()
        closeQuote()
        if (inOrdered) closeLists()
        if (!inList) { out.append("<ul>\n"); inList = true }
        out.append("<li>").append(MarkdownHtml.inline(line.trimStart().removePrefix("- "), policy)).append("</li>\n")
        return true
    }
}
