package dev.ninfenz.mobile.data

/** 轻量 HTML → Markdown：去脚本/样式，保留标题/列表/段落/换行，解码常见实体。 */
object HtmlImporter {
    fun toMarkdown(html: String): String {
        var text = html
        text = Regex("(?is)<script.*?</script>").replace(text, " ")
        text = Regex("(?is)<style.*?</style>").replace(text, " ")
        text = Regex("(?s)<!--.*?-->").replace(text, " ")
        text = Regex("(?is)<h([1-6])[^>]*>(.*?)</h\\1>").replace(text) { m ->
            "\n\n" + "#".repeat(m.groupValues[1].toInt()) + " " + strip(m.groupValues[2]).trim() + "\n\n"
        }
        text = Regex("(?is)<table[^>]*>(.*?)</table>").replace(text) { m ->
            "\n\n" + table(m.groupValues[1]) + "\n\n"
        }
        text = Regex("(?is)<li[^>]*>(.*?)</li>").replace(text) { m ->
            "\n- " + strip(m.groupValues[1]).trim()
        }
        text = Regex("(?is)<a\\s+[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>").replace(text) { m ->
            "[" + strip(m.groupValues[2]).trim() + "](" + m.groupValues[1] + ")"
        }
        text = Regex("(?is)<br\\s*/?>").replace(text, "\n")
        text = Regex("(?is)</p\\s*>").replace(text, "\n\n")
        text = strip(text)
        text = decode(text)
        return text.split('\n').joinToString("\n") { it.trim() }
            .replace(Regex("\n{3,}"), "\n\n")
            .trim()
    }

    private fun table(html: String): String {
        val rows = Regex("(?is)<tr[^>]*>(.*?)</tr>").findAll(html).map { row ->
            Regex("(?is)<t[hd][^>]*>(.*?)</t[hd]>").findAll(row.groupValues[1]).map { cell ->
                strip(cell.groupValues[1]).trim().replace("|", "\\|")
            }.toList()
        }.filter { it.isNotEmpty() }.toList()
        if (rows.isEmpty()) return ""
        val width = rows.maxOf { it.size }
        val out = StringBuilder()
        rows.forEachIndexed { index, cells ->
            out.append("| ")
            for (i in 0 until width) { out.append(cells.getOrElse(i) { "" }); if (i < width - 1) out.append(" | ") }
            out.append(" |\n")
            if (index == 0) {
                out.append("|")
                repeat(width) { out.append(" --- |") }
                out.append("\n")
            }
        }
        return out.toString().trimEnd()
    }

    private fun strip(html: String): String = Regex("(?s)<[^>]+>").replace(html, "")
        .replace('\u00A0', ' ')

    private fun decode(text: String): String = text
        .replace("&nbsp;", " ")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"")
        .replace("&#39;", "'")
        .replace("&amp;", "&")
}
