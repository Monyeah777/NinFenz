package dev.ninfenz.mobile.model

/** 从导入切片生成可分享给 AI 的 Prompt Pack；只描述样本/结构/约束，不伪造事实。 */
object PromptPack {
    fun from(sourceTitle: String, text: String, slices: List<MarkdownSlice>, samples: List<String> = emptyList()): String {
        val title = slices.firstOrNull { it.heading != null }?.heading ?: sourceTitle.ifBlank { "导入稿" }
        val outline = slices.take(12).joinToString("\n") { slice ->
            val h = slice.heading ?: "开篇"
            "- " + h + "（" + slice.blocks.size + " 块 / " + slice.charCount + " 字）"
        }
        return buildString {
            appendLine("# NF Prompt Pack · " + title)
            appendLine()
            appendLine("## 样本")
            appendLine(text.take(2000))
            appendLine()
            appendLine("## 结构")
            appendLine(outline)
            appendLine()
            if (samples.isNotEmpty()) {
                appendLine("## 样本库参考")
                samples.take(2).forEach { sample ->
                    appendLine("~~~markdown")
                    appendLine(sample.take(1200))
                    appendLine("~~~")
                }
                appendLine()
            }
            appendLine("## 约束")
            appendLine("- 保留样本中的事实与数字，不自行补充来源。")
            appendLine("- 缺失信息标记为【待核实】，不编造。")
            appendLine("- 章节顺序沿用上面的结构。")
            appendLine()
            appendLine("## 验收")
            appendLine("- 输出为 Markdown。")
            appendLine("- 每个章节都有正文，且不出现占位符。")
            appendLine("- 与样本冲突时，以样本为准并指出冲突。")
        }
    }
}
