package dev.ninfenz.mobile.data

/** Free/Pro/CCOS 分层：默认 Free 全开，不因 Pro/CCOS 关闭而锁日常能力。 */
object FeatureGate {
    enum class Tier { FREE, PRO, CCOS }

    fun tier(): Tier = Tier.FREE

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
}
