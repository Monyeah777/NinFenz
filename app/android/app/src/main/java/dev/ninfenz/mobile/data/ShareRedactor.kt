package dev.ninfenz.mobile.data

/** 分享前脱敏：移除 HTML 注释与显式 source/来源 行；不改正文语义。 */
object ShareRedactor {
    private val comment = Regex("<!--[\\s\\S]*?-->")
    private val sourceLine = Regex("(?im)^\\s*(source|来源)\\s*[:：]\\s*\\S+.*$")

    fun redact(markdown: String): String = comment.replace(markdown, "")
        .replace(sourceLine, "")
        .replace(Regex("\\n{3,}"), "\n\n")
        .trim()
}
