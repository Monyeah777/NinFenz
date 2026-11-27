package dev.ninfenz.mobile.data

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
