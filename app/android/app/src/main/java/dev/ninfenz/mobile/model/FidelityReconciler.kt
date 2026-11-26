package dev.ninfenz.mobile.model

/** 导出后对账：把 spec 章节标题与 Markdown 标题比对，给出匹配分/缺失/多出。 */
data class FidelityReconcile(
    val score: Int,
    val matched: Int,
    val expected: Int,
    val missing: List<String>,
    val extra: List<String>,
    val notes: List<String>
)

object FidelityReconciler {
    fun headings(markdown: String): List<String> = markdown.lineSequence()
        .map { it.trim() }
        .filter { it.startsWith("#") }
        .map { it.trimStart('#').trim() }
        .filter { it.isNotEmpty() }
        .toList()

    fun fromSpec(spec: MdSpec?, markdown: String): FidelityReconcile =
        reconcile(spec?.sections?.map { it.title }.orEmpty(), markdown)

    fun reconcile(expectedTitles: List<String>, markdown: String): FidelityReconcile {
        val expected = expectedTitles.distinct()
        val actual = headings(markdown)
        val actualSet = actual.toSet()
        val expectedSet = expected.toSet()
        val missing = expected.filter { it !in actualSet }
        val extra = actual.filter { it !in expectedSet }
        val matched = expected.count { it in actualSet }
        val score = if (expected.isEmpty()) 100 else matched * 100 / expected.size
        val notes = buildList {
            if (expected.isEmpty()) add("spec 没有章节标题")
            if (missing.isNotEmpty()) add("缺失 " + missing.size + " 个章节标题")
            if (extra.isNotEmpty()) add("多出 " + extra.size + " 个标题")
        }
        return FidelityReconcile(score, matched, expected.size, missing, extra, notes)
    }
}
