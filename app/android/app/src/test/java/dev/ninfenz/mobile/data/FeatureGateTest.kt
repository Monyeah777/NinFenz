package dev.ninfenz.mobile.data

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FeatureGateTest {
    @After
    fun resetTier() {
        FeatureGate.resetForTest()
    }

    @Test
    fun defaultTierMatchesEdition() {
        assertEquals(FeatureGate.defaultTier(), FeatureGate.tier())
        if (FeatureGate.defaultTier() == FeatureGate.Tier.FREE) {
            assertTrue(!FeatureGate.isProEnabled())
            assertTrue(!FeatureGate.isCcosEnabled())
        }
    }

    @Test
    fun debugTierSwitchChangesGate() {
        FeatureGate.setTierForDebug(FeatureGate.Tier.PRO)
        assertTrue(FeatureGate.allows("graph.author"))
        assertTrue(!FeatureGate.allows("ccos.task"))
        FeatureGate.setTierForDebug(FeatureGate.Tier.CCOS)
        assertTrue(FeatureGate.allows("ccos.task"))
        FeatureGate.setTierForDebug(FeatureGate.Tier.FREE)
        assertTrue(!FeatureGate.allows("graph.author"))
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
