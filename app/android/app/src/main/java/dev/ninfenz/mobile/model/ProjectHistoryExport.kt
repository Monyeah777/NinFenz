package dev.ninfenz.mobile.model

/** 项目状态历史 → Markdown 分享文本（脱敏、只含项目内已有字段）。 */
object ProjectHistoryExport {
    fun toMarkdown(project: Project): String {
        val title = project.title.replace("|", "\\|")
        val out = StringBuilder()
        out.append("# 项目历史 · ").append(title).append("\n\n")
        out.append("- 项目 ID：").append(project.id).append("\n")
        out.append("- 当前状态：").append(project.status.wire).append("\n")
        out.append("- 条目数：").append(project.history.size).append("\n\n")
        if (project.history.isEmpty()) {
            out.append("（无历史记录）\n")
            return out.toString()
        }
        out.append("| op | digest | at |\n|---|---|---|\n")
        project.history.forEach { h ->
            out.append("| ")
                .append(h.op.replace("|", "\\|"))
                .append(" | ")
                .append(h.digest.orEmpty())
                .append(" | ")
                .append(h.at.orEmpty())
                .append(" |\n")
        }
        return out.toString()
    }
}
