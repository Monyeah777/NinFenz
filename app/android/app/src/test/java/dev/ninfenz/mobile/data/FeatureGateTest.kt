package dev.ninfenz.mobile.data

import org.junit.Assert.assertTrue
import org.junit.Test

class FeatureGateTest {
    @Test
    fun proAndCcosDisabledByDefault() {
        assertTrue(!FeatureGate.isProEnabled())
        assertTrue(!FeatureGate.isCcosEnabled())
    }

    @Test
    fun freeFeaturesStayOpen() {
        assertTrue(FeatureGate.allows("import"))
        assertTrue(FeatureGate.allows("preview"))
        assertTrue(FeatureGate.allows("export"))
        assertTrue(FeatureGate.allows("share"))
        assertTrue(FeatureGate.allows("reset"))
    }
}
