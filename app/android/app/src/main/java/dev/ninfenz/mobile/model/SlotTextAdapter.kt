package dev.ninfenz.mobile.model

/**
 * 槽位文本导入适配：把 Markdown/纯文本统一成适合槽位的纯文本。
 * 规则保守、可预期：去 BOM/统一换行/去 YAML frontmatter；Markdown 去标题井号、
 * 列表符号、引用符号、强调标记、链接只留文字。
 */
object SlotTextAdapter {
    data class Adapted(
        val original: String,
        val adapted: String,
        val format: String,
        val changed: Boolean
    )

    fun normalize(raw: String): String =
        raw.removePrefix("\uFEFF").replace("\r\n", "\n").replace('\r', '\n')

    fun adapt(raw: String, fileName: String? = null): Adapted {
        val normalized = normalize(raw)
        val stripped = stripFrontMatter(normalized)
        val looksMarkdown = fileName?.lowercase()?.let { it.endsWith(".md") || it.endsWith(".markdown") } == true ||
            stripped.contains(Regex("(?m)^#{1,6}\\s")) ||
            stripped.contains(Regex("(?m)^\\s*[-*+]\\s"))
        val adapted = if (looksMarkdown) markdownToPlain(stripped) else stripped.trim()
        return Adapted(
            original = normalized.trim(),
            adapted = adapted,
            format = if (looksMarkdown) "markdown" else "text",
            changed = adapted != normalized.trim()
        )
    }

    fun stripFrontMatter(text: String): String {
        if (!text.startsWith("---\n")) return text
        val end = text.indexOf("\n---", startIndex = 4)
        if (end < 0) return text
        val after = end + 4
        return if (after < text.length && text[after] == '\n') text.substring(after + 1) else text.substring(after)
    }

    private fun markdownToPlain(text: String): String {
        val out = StringBuilder()
        for (line in text.lines()) {
            var s = line
            s = s.replace(Regex("^\\s{0,3}#{1,6}\\s+"), "")
            s = s.replace(Regex("^\\s{0,3}>\\s?"), "")
            s = s.replace(Regex("^\\s*[-*+]\\s+"), "• ")
            s = s.replace(Regex("!\\[([^]]*)]\\([^)]*\\)"), "$1")
            s = s.replace(Regex("\\[([^]]*)]\\([^)]*\\)"), "$1")
            s = s.replace(Regex("\\*\\*([^*]+)\\*\\*"), "$1")
            s = s.replace(Regex("__([^_]+)__"), "$1")
            s = s.replace(Regex("(?<!\\*)\\*([^*]+)\\*(?!\\*)"), "$1")
            s = s.replace(Regex("(?<!_)_([^_]+)_(?!_)"), "$1")
            s = s.replace(Regex("<[^>]+>"), "")
            s = s.replace(Regex("^\\s*([-*_])\\1{2,}\\s*$"), "")
            out.append(s.trimEnd()).append('\n')
        }
        return out.toString().replace(Regex("\n{3,}"), "\n\n").trim()
    }
}
