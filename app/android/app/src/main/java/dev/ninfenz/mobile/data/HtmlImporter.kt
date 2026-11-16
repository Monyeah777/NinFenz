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
        text = Regex("(?is)<li[^>]*>(.*?)</li>").replace(text) { m ->
            "\n- " + strip(m.groupValues[1]).trim()
        }
        text = Regex("(?is)<br\\s*/?>").replace(text, "\n")
        text = Regex("(?is)</p\\s*>").replace(text, "\n\n")
        text = strip(text)
        text = decode(text)
        return text.split('\n').joinToString("\n") { it.trim() }
            .replace(Regex("\n{3,}"), "\n\n")
            .trim()
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
