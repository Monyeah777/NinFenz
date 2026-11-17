package dev.ninfenz.mobile.data

import java.io.File

/** 单文件 HTML 导出：基础 Markdown 转 HTML；离线、无外部资源。 */
object HtmlExporter {
    data class Created(val file: File, val bytes: Long)

    fun export(markdown: String, title: String, outDir: File): Created {
        outDir.mkdirs()
        val target = File(outDir, "result.html")
        target.writeText(html(markdown, title), Charsets.UTF_8)
        return Created(target, target.length())
    }

    fun html(markdown: String, title: String): String {
        val body = convert(markdown.replace("\r\n", "\n"))
        val html = StringBuilder()
        html.append("<!DOCTYPE html>\n<html lang=\"zh\"><head><meta charset=\"utf-8\"/>")
        html.append("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>")
        html.append("<title>").append(esc(title)).append("</title>")
        html.append("<style>body{font-family:serif;line-height:1.7;max-width:760px;margin:2em auto;padding:0 1em;color:#222}pre{background:#f5f5f5;padding:1em;overflow:auto}code{font-family:monospace}h1,h2,h3{line-height:1.3}</style>")
        html.append("</head><body><h1>").append(esc(title)).append("</h1>\n")
        html.append(body)
        html.append("</body></html>\n")
        return html.toString()
    }

    private fun convert(markdown: String): String {
        val out = StringBuilder()
        var inCode = false
        var inList = false
        var inQuote = false
        var inOrdered = false
        var codeLang = ""
        val code = StringBuilder()
        val table = mutableListOf<List<String>>()
        var tableAlign = emptyList<String>()
        fun closeQuote() {
            if (inQuote) { out.append("</blockquote>"); inQuote = false }
        }
        fun closeLists() {
            if (inList) { out.append("</ul>\n"); inList = false }
            if (inOrdered) { out.append("</ol>\n"); inOrdered = false }
        }
        fun flushTable() {
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
                    out.append("<").append(tag).append(style).append(">").append(inline(cell)).append("</").append(tag).append(">")
                }
                out.append("</tr>")
                if (index == 0) out.append("</thead>")
            }
            if (table.size > 1) out.append("</tbody>")
            out.append("</table>")
            table.clear()
            tableAlign = emptyList()
        }
        markdown.split('\n').forEach { line ->
            if (line.trimStart().startsWith("\u0060\u0060\u0060")) {
                if (inCode) {
                    val cls = if (codeLang.isNotBlank()) " class=\"language-" + codeLang + "\"" else ""
                    out.append("<pre><code").append(cls).append(">").append(esc(code.toString().trimEnd())).append("</code></pre>\n")
                    code.clear()
                    codeLang = ""
                } else {
                    codeLang = line.trimStart().removePrefix("\u0060\u0060\u0060").trim().takeWhile { it.isLetterOrDigit() || it == '_' || it == '-' }
                }
                inCode = !inCode
                return@forEach
            }
            if (inCode) { code.append(line).append('\n'); return@forEach }
            if (line.isBlank()) {
                closeLists()
                flushTable()
                closeQuote()
                return@forEach
            }
            val trimmed = line.trim()
            if (trimmed.startsWith("> ")) {
                flushTable()
                closeLists()
                if (!inQuote) { out.append("<blockquote>"); inQuote = true }
                out.append("<p>").append(inline(trimmed.removePrefix("> "))).append("</p>")
                return@forEach
            }
            val ordered = Regex("^\\s*\\d+\\.\\s+(.+)$").find(trimmed)
            if (ordered != null) {
                flushTable()
                closeQuote()
                if (inList) { out.append("</ul>\n"); inList = false }
                if (!inOrdered) { out.append("<ol>"); inOrdered = true }
                out.append("<li>").append(inline(ordered.groupValues[1])).append("</li>")
                return@forEach
            }
            if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
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
                return@forEach
            }
            if (Regex("^-{3,}$").matches(trimmed)) {
                flushTable()
                closeQuote()
                closeLists()
                out.append("<hr/>")
                return@forEach
            }
            val h = Regex("^(#{1,6})\\s+(.+)$").find(line)
            if (h != null) {
                flushTable()
                closeQuote()
                closeLists()
                val level = h.groupValues[1].length
                out.append("<h").append(level).append(">").append(inline(h.groupValues[2])).append("</h").append(level).append(">\n")
                return@forEach
            }
            if (line.trimStart().startsWith("- ")) {
                flushTable()
                closeQuote()
                if (inOrdered) closeLists()
                if (!inList) { out.append("<ul>\n"); inList = true }
                out.append("<li>").append(inline(line.trimStart().removePrefix("- "))).append("</li>\n")
                return@forEach
            }
            closeLists()
            flushTable()
            closeQuote()
            out.append("<p>").append(inline(line)).append("</p>\n")
        }
        flushTable()
        closeQuote()
        closeLists()
        if (inCode && code.isNotEmpty()) out.append("<pre><code>").append(esc(code.toString().trimEnd())).append("</code></pre>\n")
        return out.toString()
    }

    private fun inline(s: String): String {
        var text = esc(s)
        text = Regex("\u0060([^\u0060]+)\u0060").replace(text, "<code>$1</code>")
        text = Regex("\\*\\*([^*]+)\\*\\*").replace(text, "<strong>$1</strong>")
        text = Regex("\\*([^*]+)\\*").replace(text, "<em>$1</em>")
        text = Regex("~~([^~]+)~~").replace(text, "<del>$1</del>")
        text = Regex("!\\[([^\\]]*)\\]\\(([^)]+)\\)").replace(text) { match ->
            val src = match.groupValues[2]
            if (src.startsWith("http://") || src.startsWith("https://") || src.startsWith("data:image/")) {
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

    private fun esc(s: String): String = s
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")
}
