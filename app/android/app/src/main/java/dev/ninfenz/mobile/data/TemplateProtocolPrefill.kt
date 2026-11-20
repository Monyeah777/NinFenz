package dev.ninfenz.mobile.data

/** 模板槽位行 → 槽位名到示例；只做显式行解析，不猜语义。 */
object TemplateProtocolPrefill {
    fun parse(markdown: String): Map<String, String> = Regex("(?m)^- (SLT-\\S+) (.+?)(?:（[^）]*）)?[：:](.+)$")
        .findAll(markdown)
        .associate { m -> m.groupValues[2].trim() to m.groupValues[3].trim() }
        .filterValues { it.isNotBlank() }
}
