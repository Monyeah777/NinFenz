package dev.ninfenz.mobile.data

/** Free/Pro/CCOS 分层空实现：默认 Free 全开，不因 Pro/CCOS 关闭而锁日常能力。 */
object FeatureGate {
    enum class Tier { FREE, PRO, CCOS }

    fun tier(): Tier = Tier.FREE

    fun isProEnabled(): Boolean = false

    fun isCcosEnabled(): Boolean = false

    /** 当前默认全开；未来 Pro/CCOS 也只能加深度，不能回锁 Free。 */
    fun allows(@Suppress("UNUSED_PARAMETER") feature: String): Boolean = true
}
