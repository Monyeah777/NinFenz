package dev.ninfenz.mobile.data

import java.io.File

/** 单文件 HTML 导出：基础 Markdown 转 HTML；离线、无外部资源。 */
object HtmlExporter {
    data class Created(val file: File, val bytes: Long)

    fun export(markdown: String, title: String, outDir: File): Created {
        outDir.mkdirs()
        val target = File(outDir, "result.html")
        val body = convert(markdown.replace("\r\n", "\n"))
        val html = StringBuilder()
        html.append("<!DOCTYPE html>\n<html lang=\"zh\"><head><meta charset=\"utf-8\"/>")
        html.append("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>")
        html.append("<title>").append(esc(title)).append("</title>")
        html.append("<style>body{font-family:serif;line-height:1.7;max-width:760px;margin:2em auto;padding:0 1em;color:#222}pre{background:#f5f5f5;padding:1em;overflow:auto}code{font-family:monospace}h1,h2,h3{line-height:1.3}</style>")
        html.append("</head><body><h1>").append(esc(title)).append("</h1>\n")
        html.append(body)
        html.append("</body></html>\n")
        target.writeText(html.toString(), Charsets.UTF_8)
        return Created(target, target.length())
    }

    private fun convert(markdown: String): String {
        val out = StringBuilder()
        var inCode = false
        var inList = false
        val code = StringBuilder()
        markdown.split('\n').forEach { line ->
            if (line.trimStart().startsWith("\u0060\u0060\u0060")) {
                if (inCode) {
                    out.append("<pre><code>").append(esc(code.toString().trimEnd())).append("</code></pre>\n")
                    code.clear()
                }
                inCode = !inCode
                return@forEach
            }
            if (inCode) { code.append(line).append('\n'); return@forEach }
            if (line.isBlank()) {
                if (inList) { out.append("</ul>\n"); inList = false }
                return@forEach
            }
            val h = Regex("^(#{1,6})\\s+(.+)$").find(line)
            if (h != null) {
                if (inList) { out.append("</ul>\n"); inList = false }
                val level = h.groupValues[1].length
                out.append("<h").append(level).append(">").append(inline(h.groupValues[2])).append("</h").append(level).append(">\n")
                return@forEach
            }
            if (line.trimStart().startsWith("- ")) {
                if (!inList) { out.append("<ul>\n"); inList = true }
                out.append("<li>").append(inline(line.trimStart().removePrefix("- "))).append("</li>\n")
                return@forEach
            }
            if (inList) { out.append("</ul>\n"); inList = false }
            out.append("<p>").append(inline(line)).append("</p>\n")
        }
        if (inList) out.append("</ul>\n")
        if (inCode && code.isNotEmpty()) out.append("<pre><code>").append(esc(code.toString().trimEnd())).append("</code></pre>\n")
        return out.toString()
    }

    private fun inline(s: String): String {
        var text = esc(s)
        text = Regex("\\\\*\\\\*([^*]+)\\\\*\\\\*").replace(text, "<strong>$1</strong>")
        text = Regex("\\\\*([^*]+)\\\\*").replace(text, "<em>$1</em>")
        return text
    }

    private fun esc(s: String): String = s
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")
}
