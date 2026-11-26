package dev.ninfenz.mobile.data

/** 模块开关的唯一读口；edition 门仍由 FeatureGate 负责，二者不互相冒充。 */
object CapabilityRegistry {
    @Volatile
    private var prefs: NfPrefs = NfPrefs()

    @Volatile
    var revision: Int = -1
        private set

    fun install(next: NfPrefs) {
        prefs = next
        revision = next.revision
    }

    fun current(): NfPrefs = prefs

    fun isEnabled(capability: Capability): Boolean = prefs.modules.enabled(capability)

    fun allows(capability: Capability, editionFeature: String? = null): Boolean =
        isEnabled(capability) && (editionFeature == null || FeatureGate.allows(editionFeature))

    fun require(capability: Capability, editionFeature: String? = null): Boolean =
        allows(capability, editionFeature)

    fun resetForTest() {
        prefs = NfPrefs()
        revision = -1
    }
}
