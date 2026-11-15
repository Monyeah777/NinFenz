package dev.ninfenz.studio.render

/**
 * 轻量 Markdown 渲染（打印/预览）：确定性、无网络、无第三方依赖。
 * 只服务「预览/打印」，Markdown 本体仍是产物真源。
 */
object MarkdownRenderer {

    fun toPlainText(markdown: String): String {
        val out = StringBuilder()
        var inFence = false
        for (raw in markdown.lines()) {
            val trimmed = raw.trim()
            if (trimmed.startsWith("```")) {
                inFence = !inFence
                out.appendLine(if (inFence) "[code]" else "[/code]")
                continue
            }
            if (inFence) {
                out.appendLine("    " + raw)
                continue
            }
            when {
                trimmed.startsWith("###### ") -> heading(out, trimmed.removePrefix("###### "), 6)
                trimmed.startsWith("##### ") -> heading(out, trimmed.removePrefix("##### "), 5)
                trimmed.startsWith("#### ") -> heading(out, trimmed.removePrefix("#### "), 4)
                trimmed.startsWith("### ") -> heading(out, trimmed.removePrefix("### "), 3)
                trimmed.startsWith("## ") -> heading(out, trimmed.removePrefix("## "), 2)
                trimmed.startsWith("# ") -> heading(out, trimmed.removePrefix("# "), 1)
                trimmed.startsWith("- ") || trimmed.startsWith("* ") -> out.appendLine("  • " + inline(trimmed.substring(2)))
                trimmed.startsWith("> ") -> out.appendLine("  ｜ " + inline(trimmed.removePrefix("> ")))
                else -> out.appendLine(inline(raw))
            }
        }
        return out.toString().trimEnd()
    }

    private fun heading(out: StringBuilder, title: String, level: Int) {
        if (level <= 2) {
            out.appendLine()
            out.appendLine(title.uppercase())
            out.appendLine("=".repeat(maxOf(3, title.length)))
        } else {
            out.appendLine()
            out.appendLine("【" + title + "】")
        }
    }

    /** 纯文本行内标记清理（不保留强调语义，打印可读优先）。 */
    private fun inline(text: String): String = text
        .replace("**", "")
        .replace("__", "")

    fun toHtml(markdown: String): String {
        val body = StringBuilder()
        var inFence = false
        val code = StringBuilder()
        var inList = false
        fun closeList() {
            if (inList) {
                body.appendLine("</ul>")
                inList = false
            }
        }
        for (raw in markdown.lines()) {
            val trimmed = raw.trim()
            if (trimmed.startsWith("```")) {
                if (inFence) {
                    body.appendLine("<pre><code>" + escape(code.toString()) + "</code></pre>")
                    code.setLength(0)
                } else {
                    closeList()
                }
                inFence = !inFence
                continue
            }
            if (inFence) {
                code.appendLine(raw)
                continue
            }
            when {
                trimmed.isEmpty() -> closeList()
                trimmed.startsWith("- ") || trimmed.startsWith("* ") -> {
                    if (!inList) {
                        body.appendLine("<ul>")
                        inList = true
                    }
                    body.appendLine("<li>" + inlineHtml(trimmed.substring(2)) + "</li>")
                }
                trimmed.startsWith("#") -> {
                    closeList()
                    val level = trimmed.takeWhile { it == '#' }.length.coerceIn(1, 6)
                    val title = trimmed.dropWhile { it == '#' }.trim()
                    body.appendLine("<h" + level + ">" + inlineHtml(title) + "</h" + level + ">")
                }
                else -> {
                    closeList()
                    body.appendLine("<p>" + inlineHtml(trimmed) + "</p>")
                }
            }
        }
        closeList()
        if (inFence) body.appendLine("<pre><code>" + escape(code.toString()) + "</code></pre>")
        return "<!DOCTYPE html><html><head><meta charset=\"utf-8\"><title>NF Studio 打印</title>" +
            "<style>body{font-family:Georgia,serif;max-width:46em;margin:2em auto;line-height:1.5}" +
            "pre{background:#f4f4f4;padding:8px;overflow:auto}code{font-family:Consolas,monospace}</style>" +
            "</head><body>" + body.toString() + "</body></html>"
    }

    /** 强调只处理成对 **（不使用正则/回溯，输出确定）。 */
    private fun inlineHtml(text: String): String {
        val escaped = escape(text)
        val parts = escaped.split("**")
        if (parts.size < 3) return escaped
        val sb = StringBuilder()
        parts.forEachIndexed { index, part ->
            if (index % 2 == 1) sb.append("<strong>").append(part).append("</strong>") else sb.append(part)
        }
        return sb.toString()
    }

    fun escape(text: String): String = text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")
}
