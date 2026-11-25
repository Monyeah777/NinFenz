package dev.ninfenz.mobile.data

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FeaturePolicyTest {
    @Test
    fun freeIsAlwaysOpen() {
        for (tier in FeaturePolicy.Tier.values()) {
            assertTrue(FeaturePolicy.allows("import", tier))
            assertTrue(FeaturePolicy.allows("export.md", tier))
            assertTrue(FeaturePolicy.allows("settings", tier))
        }
    }

    @Test
    fun proLockedOnFree() {
        assertFalse(FeaturePolicy.allows("graph.author", FeaturePolicy.Tier.FREE))
        assertTrue(FeaturePolicy.allows("graph.author", FeaturePolicy.Tier.PRO))
        assertTrue(FeaturePolicy.allows("graph.author", FeaturePolicy.Tier.CCOS))
    }

    @Test
    fun auditIsProOnly() {
        for (feature in listOf("audit.validate", "audit.review", "audit.preservation", "audit.pdfua", "audit.ccos")) {
            assertFalse(FeaturePolicy.allows(feature, FeaturePolicy.Tier.FREE))
            assertTrue(FeaturePolicy.allows(feature, FeaturePolicy.Tier.PRO))
        }
    }

    @Test
    fun ccosOnlyOnCcos() {
        assertFalse(FeaturePolicy.allows("ccos.task", FeaturePolicy.Tier.FREE))
        assertFalse(FeaturePolicy.allows("ccos.task", FeaturePolicy.Tier.PRO))
        assertTrue(FeaturePolicy.allows("ccos.task", FeaturePolicy.Tier.CCOS))
    }

    @Test
    fun unknownStaysFree() {
        assertTrue(FeaturePolicy.allows("future.feature", FeaturePolicy.Tier.FREE))
        assertTrue(FeaturePolicy.allows("future.feature", FeaturePolicy.Tier.PRO))
    }

    @Test
    fun gateDelegatesByTier() {
        assertTrue(FeatureGate.allows("import", FeatureGate.Tier.FREE))
        assertFalse(FeatureGate.allows("graph.author", FeatureGate.Tier.FREE))
        assertTrue(FeatureGate.allows("graph.author", FeatureGate.Tier.PRO))
        assertFalse(FeatureGate.allows("ccos.task", FeatureGate.Tier.PRO))
        assertTrue(FeatureGate.allows("ccos.task", FeatureGate.Tier.CCOS))
    }
}
