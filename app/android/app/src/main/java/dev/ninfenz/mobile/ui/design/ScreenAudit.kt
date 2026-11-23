package dev.ninfenz.mobile.ui.design

/** 单屏证据；没有截图的项填 null，审计不得把 null 当通过。 */
data class ScreenEvidence(
    val typeSizes: Set<Float>,
    val weights: Set<Int>,
    val primaryActions: Int,
    val accentAreaRatio: Double,
    val spacing: List<Int>,
    val minContrast: Double,
    val stateHasText: Boolean,
    val stateHasShape: Boolean,
    val stateHasColor: Boolean,
    val scale200NoClip: Boolean?,
    val composition: List<CompositionSlot>,
    val motionMs: Set<Int>,
    val feedbackMs: Int?
)

data class AuditIssue(val id: String, val detail: String)

data class AuditResult(val passed: Int, val total: Int, val issues: List<AuditIssue>) {
    val score: Int get() = if (total == 0) 0 else (passed * 100 / total)
    val blocked: Boolean get() = issues.any { it.id == "S-CONTRAST" || it.id == "S-CLIP" }
}

object ScreenAudit {
    /**
     * 12 项/屏；不可用证据（null）不计通过。分数只用于同一套证据内比较，
     * 不跨设备/跨截图缩放比较。
     */
    fun evaluate(e: ScreenEvidence): AuditResult {
        val issues = mutableListOf<AuditIssue>()
        var passed = 0
        fun check(id: String, ok: Boolean, detail: String) {
            if (ok) passed++ else issues += AuditIssue(id, detail)
        }
        check("S-TYPE", e.typeSizes.size <= 4, "type sizes=${e.typeSizes}")
        check("S-WEIGHT", e.weights.size <= 2, "weights=${e.weights}")
        check("S-ACTION", e.primaryActions <= 1, "primary actions=${e.primaryActions}")
        check("S-ACCENT", SalienceBudget.accepts(e.primaryActions, e.accentAreaRatio), "accent area=${e.accentAreaRatio}")
        check("S-GRID", e.spacing.all { it % 4 == 0 }, "spacing off grid=${e.spacing.filter { it % 4 != 0 }}")
        check("S-PROX", Proximity.isSeparated(), "proximity ratio=${Proximity.ratio()}")
        check("S-CONTRAST", e.minContrast >= 4.5, "min contrast=${e.minContrast}")
        check("S-STATE", e.stateHasText && e.stateHasShape && e.stateHasColor, "state channels text/shape/color")
        check("S-CLIP", e.scale200NoClip == true, "200% clip evidence=${e.scale200NoClip}")
        check("S-COMP", Composition.validate(e.composition).isEmpty(), Composition.validate(e.composition).joinToString())
        check("S-MOTION", e.motionMs.isNotEmpty() && e.motionMs.all { it in Motion.all }, "motion=${e.motionMs}")
        check("S-FEEDBACK", e.feedbackMs != null && Feedback.isFast(e.feedbackMs), "feedback=${e.feedbackMs}")
        return AuditResult(passed, 12, issues)
    }
}
