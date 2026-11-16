package dev.ninfenz.mobile.model

/** 两个项目文档的只读差异（状态/引用/评审/历史），用于人工对比。 */
object ProjectDiff {
    data class Change(val field: String, val before: String, val after: String)
    data class Report(val changes: List<Change>, val historyOnlyBefore: List<String>, val historyOnlyAfter: List<String>) {
        val hasChanges: Boolean get() = changes.isNotEmpty() || historyOnlyBefore.isNotEmpty() || historyOnlyAfter.isNotEmpty()
    }

    fun compare(before: Project, after: Project): Report {
        val changes = mutableListOf<Change>()
        fun add(field: String, a: String?, b: String?) {
            val x = a.orEmpty()
            val y = b.orEmpty()
            if (x != y) changes.add(Change(field, x.ifBlank { "-" }, y.ifBlank { "-" }))
        }
        add("status", before.status.wire, after.status.wire)
        add("base_pack", before.refs.basePackId + "@" + before.refs.basePackVersion, after.refs.basePackId + "@" + after.refs.basePackVersion)
        add("protocol_digest", before.refs.protocolDigest, after.refs.protocolDigest)
        add("graph_digest", before.refs.graphDigest, after.refs.graphDigest)
        add("spec_digest", before.refs.specDigest, after.refs.specDigest)
        add("assembly_digest", before.refs.assemblyDigest, after.refs.assemblyDigest)
        add("review", before.review.state, after.review.state)
        add("reviewer", before.review.reviewer, after.review.reviewer)
        add("review_note", before.review.note, after.review.note)
        add("history_count", before.history.size.toString(), after.history.size.toString())
        val a = before.history.map { it.op }.toSet()
        val b = after.history.map { it.op }.toSet()
        return Report(
            changes = changes,
            historyOnlyBefore = (a - b).sorted(),
            historyOnlyAfter = (b - a).sorted()
        )
    }
}
