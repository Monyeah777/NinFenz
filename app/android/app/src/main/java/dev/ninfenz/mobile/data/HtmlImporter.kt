package dev.ninfenz.mobile.data

/** 轻量 HTML → Markdown：去脚本/样式，保留标题/列表/段落/换行，解码常见实体。 */
object HtmlImporter {
    fun decode(bytes: ByteArray): String {
        TextEncoding.decode(bytes)?.let { return it.text }
        val head = String(bytes, 0, minOf(bytes.size, 4096), Charsets.ISO_8859_1)
        val charset = Regex("(?i)<meta[^>]+charset=[\"']?([A-Za-z0-9._-]+)").find(head)?.groupValues?.getOrNull(1)
        val cs = charset?.let { runCatching { java.nio.charset.Charset.forName(it) }.getOrNull() }
        return if (cs != null) String(bytes, cs) else TextEncoding.decodeText(bytes)
    }

    fun toMarkdown(html: String): String {
        var text = html
        text = Regex("(?is)<script.*?</script>").replace(text, " ")
        text = Regex("(?is)<style.*?</style>").replace(text, " ")
        text = Regex("(?s)<!--.*?-->").replace(text, " ")
        text = Regex("(?is)<a\\s+[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>").replace(text) { m ->
            val target = m.groupValues[1]
            if (!SafeLink.allowed(target)) strip(m.groupValues[2]).trim()
            else "[" + strip(m.groupValues[2]).trim() + "](" + target + ")"
        }
        text = Regex("(?is)<(?:b|strong)[^>]*>(.*?)</(?:b|strong)>").replace(text) { m ->
            "**" + strip(m.groupValues[1]).trim() + "**"
        }
        text = Regex("(?is)<(?:i|em)[^>]*>(.*?)</(?:i|em)>").replace(text) { m ->
            "*" + strip(m.groupValues[1]).trim() + "*"
        }
        text = Regex("(?is)<(?:s|strike|del)[^>]*>(.*?)</(?:s|strike|del)>").replace(text) { m ->
            "~~" + strip(m.groupValues[1]).trim() + "~~"
        }
        text = Regex("(?is)<img[^>]*>").replace(text) { m ->
            val tag = m.value
            val src = Regex("(?is)src=[\"']([^\"']+)[\"']").find(tag)?.groupValues?.getOrNull(1).orEmpty()
            val alt = Regex("(?is)alt=[\"']([^\"']*)[\"']").find(tag)?.groupValues?.getOrNull(1).orEmpty()
            if (src.isBlank()) "" else "![" + alt + "](" + src + ")"
        }
        text = lists(text)
        text = Regex("(?is)<h([1-6])[^>]*>(.*?)</h\\1>").replace(text) { m ->
            "\n\n" + "#".repeat(m.groupValues[1].toInt()) + " " + strip(m.groupValues[2]).trim() + "\n\n"
        }
        text = Regex("(?is)<pre[^>]*>(.*?)</pre>").replace(text) { m ->
            "\n\n```\n" + decode(strip(m.groupValues[1])).trim('\n') + "\n```\n\n"
        }
        text = Regex("(?is)<code[^>]*>(.*?)</code>").replace(text) { m ->
            "`" + decode(strip(m.groupValues[1])).trim() + "`"
        }
        text = Regex("(?is)<blockquote[^>]*>(.*?)</blockquote>").replace(text) { m ->
            val content = decode(strip(m.groupValues[1])).trim()
            "\n\n" + content.split('\n').joinToString("\n") { "> " + it.trim() } + "\n\n"
        }
        text = Regex("(?is)<table[^>]*>(.*?)</table>").replace(text) { m ->
            "\n\n" + table(m.groupValues[1]) + "\n\n"
        }
        text = Regex("(?is)<hr\\s*/?>").replace(text, "\n\n---\n\n")
        text = Regex("(?is)<br\\s*/?>").replace(text, "\n")
        text = Regex("(?is)</p\\s*>").replace(text, "\n\n")
        text = strip(text)
        text = decode(text)
        return text.split('\n').joinToString("\n") { it.trimEnd() }
            .replace(Regex("\n{3,}"), "\n\n")
            .trim()
    }

    private fun lists(html: String): String {
        val out = StringBuilder()
        var index = 0
        while (index < html.length) {
            val m = Regex("(?i)<(ul|ol)(\\s[^>]*)?>").find(html, index)
            if (m == null) {
                out.append(html.substring(index))
                break
            }
            out.append(html.substring(index, m.range.first))
            val tag = m.groupValues[1].lowercase()
            val close = findClose(html, m.range.last + 1)
            if (close < 0) {
                out.append(html.substring(m.range.first))
                break
            }
            out.append(renderList(tag, m.value, html.substring(m.range.last + 1, close), 0))
            index = close + ("</" + tag + ">").length
        }
        return out.toString()
    }

    private fun findClose(html: String, start: Int): Int {
        val re = Regex("(?i)</?(ul|ol)\\b[^>]*>")
        var depth = 1
        for (t in re.findAll(html, start)) {
            if (t.value.startsWith("</")) depth-- else depth++
            if (depth == 0) return t.range.first
        }
        return -1
    }

    private fun renderList(tag: String, open: String, inner: String, depth: Int): String {
        val items = mutableListOf<String>()
        var pos = 0
        while (true) {
            val li = Regex("(?i)<li(\\s[^>]*)?>").find(inner, pos) ?: break
            val close = findLiClose(inner, li.range.last + 1)
            if (close < 0) break
            items.add(inner.substring(li.range.last + 1, close))
            pos = close + 5
        }
        if (items.isEmpty()) return ""
        val start = Regex("(?i)start=[\"']?(\\d+)").find(open)?.groupValues?.getOrNull(1)?.toIntOrNull() ?: 1
        return items.mapIndexed { i, item ->
            renderItem(item, if (tag == "ol") (start + i).toString() + ". " else "- ", depth)
        }.joinToString("\n")
    }

    private fun findLiClose(html: String, start: Int): Int {
        val re = Regex("(?i)</?li\\b[^>]*>")
        var depth = 1
        for (t in re.findAll(html, start)) {
            if (t.value.startsWith("</")) depth-- else depth++
            if (depth == 0) return t.range.first
        }
        return -1
    }

    private fun renderItem(item: String, marker: String, depth: Int): String {
        val out = StringBuilder()
        var index = 0
        while (index < item.length) {
            val m = Regex("(?i)<(ul|ol)(\\s[^>]*)?>").find(item, index)
            if (m == null) {
                out.append(item.substring(index))
                break
            }
            out.append(item.substring(index, m.range.first))
            val tag = m.groupValues[1].lowercase()
            val close = findClose(item, m.range.last + 1)
            if (close < 0) {
                out.append(item.substring(m.range.first))
                break
            }
            out.append("\n").append(renderList(tag, m.value, item.substring(m.range.last + 1, close), depth + 1))
            index = close + ("</" + tag + ">").length
        }
        val text = strip(out.toString()).trim()
        return "  ".repeat(depth) + marker + text
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

    private fun decode(text: String): String {
        val numeric = Regex("&#(x?[0-9A-Fa-f]+);").replace(text) { m ->
            val raw = m.groupValues[1]
            val code = if (raw.startsWith("x", true)) raw.drop(1).toIntOrNull(16) else raw.toIntOrNull()
            code?.takeIf { it in 1..0x10FFFF }?.let { String(Character.toChars(it)) } ?: m.value
        }
        return numeric
            .replace("&nbsp;", " ")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"")
        .replace("&#39;", "'")
        .replace("&amp;", "&")
}
}
