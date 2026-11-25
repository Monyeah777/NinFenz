package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.BuildConfig

/** Daily/Pro/CCOS 分层：默认 Daily 全开日常能力，审计面只在 Pro/CCOS。 */
object FeatureGate {
    enum class Tier { FREE, PRO, CCOS }

    private val initialTier: Tier = when (BuildConfig.NF_EDITION) {
        "pro" -> Tier.PRO
        "ccos" -> Tier.CCOS
        else -> Tier.FREE
    }

    @Volatile
    private var activeTier: Tier = initialTier

    fun edition(): String = BuildConfig.NF_EDITION

    fun tier(): Tier = activeTier

    fun defaultTier(): Tier = initialTier

    /** 仅用于调试/自检切换；发布版没有购买入口，仍默认 Daily。 */
    fun setTierForDebug(tier: Tier) {
        activeTier = tier
    }

    fun resetForTest() {
        activeTier = initialTier
    }

    fun isProEnabled(): Boolean = tier() != Tier.FREE

    fun isCcosEnabled(): Boolean = tier() == Tier.CCOS

    /** Free 永远放行；Pro/CCOS 只加深度，不回锁 Free。 */
    fun allows(feature: String): Boolean = allows(feature, tier())

    fun allows(feature: String, tier: Tier): Boolean =
        FeaturePolicy.allows(
            feature,
            when (tier) {
                Tier.FREE -> FeaturePolicy.Tier.FREE
                Tier.PRO -> FeaturePolicy.Tier.PRO
                Tier.CCOS -> FeaturePolicy.Tier.CCOS
            }
        )

    fun require(feature: String): Boolean = allows(feature)

    fun auditEnabled(): Boolean = allows("audit.validate")
}
