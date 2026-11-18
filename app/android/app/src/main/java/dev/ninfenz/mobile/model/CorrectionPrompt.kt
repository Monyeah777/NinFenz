package dev.ninfenz.mobile.model

/** 把校验报告转成给 AI 的修正请求；只描述报告里的问题，不扩写事实。 */
object CorrectionPrompt {
    fun build(markdown: String, report: ValidateReport): String {
        val issues = report.issues.take(12)
        return buildString {
            appendLine("# NF 修正请求")
            appendLine()
            appendLine("## 校验结论")
            appendLine("- verdict: " + report.verdict)
            appendLine("- issues: " + report.issues.size)
            appendLine()
            appendLine("## 需要修正")
            if (issues.isEmpty()) {
                appendLine("- 无")
            } else {
                issues.forEach { issue ->
                    appendLine("- [" + issue.code + "] " + (issue.path ?: "-") + "：" + issue.message)
                    val fix = issue.fix
                    if (fix.isNotBlank()) appendLine("  - 修复：" + fix)
                }
            }
            appendLine()
            appendLine("## 原文")
            appendLine(markdown.take(6000))
            appendLine()
            appendLine("## 要求")
            appendLine("- 只修正上面列出的问题，不改写无关段落。")
            appendLine("- 不新增原文没有的事实、数字或来源。")
            appendLine("- 输出完整 Markdown，而不是 diff。")
        }
    }
}
