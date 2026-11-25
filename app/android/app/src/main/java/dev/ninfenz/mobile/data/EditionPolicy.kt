package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.ui.shell.Detail
import dev.ninfenz.mobile.ui.shell.ShellState

/** Daily/Pro 路由策略：Daily 不暴露 Pro 审计详情，进程恢复/深链也走这里。 */
object EditionRoutePolicy {
    fun detailFeature(detail: Detail?): String? = when (detail) {
        is Detail.Review -> "audit.review"
        Detail.Ccos -> "audit.ccos"
        is Detail.PackBuilder -> "audit.pack.studio"
        Detail.PackUpdate -> "audit.pack.trust"
        Detail.DecisionLog -> "audit.decision"
        else -> null
    }

    fun isAllowed(detail: Detail?): Boolean {
        val feature = detailFeature(detail) ?: return true
        return FeatureGate.allows(feature)
    }

    /** 被拒绝时回退到安全落点：评审退回项目，Pack Studio 退回 Pack 中心，其余回根。 */
    fun sanitize(state: ShellState): ShellState {
        val detail = state.detail ?: return state
        if (isAllowed(detail)) return state
        val fallback: Detail? = when (detail) {
            is Detail.Review -> Detail.Project(detail.id)
            is Detail.PackBuilder -> Detail.PackCenter
            else -> null
        }
        return state.copy(detail = fallback)
    }
}

/** 导出策略：Daily 不要求 L1、不做审计复现；Pro 保留完整 gate。 */
data class ExportPolicy(
    val requireValidation: Boolean,
    val verifyArtifacts: Boolean,
    val allowPdfUa: Boolean,
    val allowPreservation: Boolean,
    val allowBatchAudit: Boolean
) {
    companion object {
        fun current(): ExportPolicy {
            val pro = FeatureGate.auditEnabled()
            return if (pro) {
                ExportPolicy(true, true, true, true, true)
            } else {
                ExportPolicy(false, false, false, false, false)
            }
        }
    }
}

/** 审计写盘唯一闸门，避免只隐藏按钮。 */
object AuditGate {
    fun canWrite(feature: String): Boolean = FeatureGate.allows(feature)
}
