package dev.ninfenz.mobile.data

/** PDF 基础文本预处理：去 Markdown 标记、标题符号、链接/图片语法与代码围栏。 */
object PdfMarkdown {
    fun lines(markdown: String): List<String> {
        val out = mutableListOf<String>()
        var inCode = false
        for (raw in markdown.replace("\r\n", "\n").split('\n')) {
            val trimmed = raw.trim()
            if (trimmed.startsWith("\u0060\u0060\u0060") || trimmed.startsWith("~~~")) {
                inCode = !inCode
                continue
            }
            if (inCode) {
                out.add(raw)
                continue
            }
            if (trimmed.isEmpty()) continue
            val hashes = trimmed.takeWhile { it == '#' }.length
            if (hashes in 1..6) {
                out.add(inline(trimmed.substring(hashes).trim()))
                continue
            }
            if (trimmed.startsWith("- ") || trimmed.startsWith("* ") || trimmed.startsWith("+ ")) {
                out.add("• " + inline(trimmed.substring(2).trim()))
                continue
            }
            out.add(inline(trimmed))
        }
        return out
    }

    fun inline(s: String): String {
        var text = s
        text = Regex("!\\[([^\\]]*)\\]\\([^)]*\\)").replace(text, "$1")
        text = Regex("\\[([^\\]]*)\\]\\([^)]*\\)").replace(text, "$1")
        text = text.replace("**", "").replace("__", "").replace("~~", "").replace("\u0060", "")
        text = text.replace("*", "")
        return text.trim()
    }
}
