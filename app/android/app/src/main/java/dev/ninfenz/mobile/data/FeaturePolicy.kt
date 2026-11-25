package dev.ninfenz.mobile.data

/** M24：策略即代码。规则是数据；未知能力默认 Free，避免误锁日常路径。 */
object FeaturePolicy {
    enum class Tier { FREE, PRO, CCOS }

    data class Rule(val id: String, val minTier: Tier)

    private val free = setOf(
        "import", "share", "preview", "undo", "templates",
        "export.md", "export.zip", "export.docx", "export.pdf", "export.epub",
        "export.html", "export.json", "export.skill", "draft.project",
        "ocr", "history", "settings"
    )

    private val pro = setOf(
        "audit.validate", "audit.review", "audit.handoff", "audit.signoff",
        "audit.preservation", "audit.repro", "audit.pdfua", "audit.decision",
        "audit.pack.trust", "audit.pack.studio", "audit.ccos",
        "graph.author", "batch.assemble", "contract.sign", "policy.code",
        "capability.share", "prompt.compile", "cross.corpus", "audit.trace"
    )

    private val ccos = setOf(
        "ccos.task", "ccos.provider", "ccos.agent", "ccos.schedule",
        "ccos.trace", "ccos.budget"
    )

    val rules: Map<String, Rule> =
        (free.map { it to Rule(it, Tier.FREE) } +
            pro.map { it to Rule(it, Tier.PRO) } +
            ccos.map { it to Rule(it, Tier.CCOS) }).toMap()

    fun rule(feature: String): Rule = rules[feature] ?: Rule(feature, Tier.FREE)

    fun allows(feature: String, tier: Tier): Boolean {
        val min = rule(feature).minTier
        return when (min) {
            Tier.FREE -> true
            Tier.PRO -> tier == Tier.PRO || tier == Tier.CCOS
            Tier.CCOS -> tier == Tier.CCOS
        }
    }
}
