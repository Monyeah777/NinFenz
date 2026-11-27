package dev.ninfenz.mobile.ui.shell

import dev.ninfenz.mobile.data.Capability
import dev.ninfenz.mobile.data.CapabilityRegistry
import dev.ninfenz.mobile.data.FeatureGate

/** Daily/Pro 路由策略 + 用户模块门；Daily 不暴露 Pro 审计详情，模块关闭时也不放行。
 *  从 data 包上移到 ui.shell：它依赖 ShellState/Detail（UI 导航状态），留在 data 会造成 data -> ui 反向依赖。 */
object EditionRoutePolicy {
    fun detailFeature(detail: Detail?): String? = when (detail) {
        is Detail.Review -> "audit.review"
        Detail.Ccos -> "audit.ccos"
        is Detail.PackBuilder -> "audit.pack.studio"
        Detail.PackUpdate -> "audit.pack.trust"
        Detail.DecisionLog -> "audit.decision"
        else -> null
    }

    fun detailCapability(detail: Detail?): Capability? = when (detail) {
        Detail.Search -> Capability.SEARCH
        Detail.NfDocMerge -> Capability.MERGE
        else -> null
    }

    fun isAllowed(detail: Detail?): Boolean {
        val feature = detailFeature(detail) ?: return capabilityAllowed(detail)
        return FeatureGate.allows(feature) && capabilityAllowed(detail)
    }

    private fun capabilityAllowed(detail: Detail?): Boolean =
        detailCapability(detail)?.let { CapabilityRegistry.isEnabled(it) } ?: true

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
