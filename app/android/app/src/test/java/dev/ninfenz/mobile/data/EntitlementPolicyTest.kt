package dev.ninfenz.mobile.data

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class EntitlementPolicyTest {
    @After
    fun resetTier() {
        FeatureGate.resetForTest()
    }

    @Test
    fun editionMapsToTier() {
        assertEquals(FeatureGate.Tier.FREE, EntitlementPolicy.tierFor(null))
        assertEquals(FeatureGate.Tier.FREE, EntitlementPolicy.tierFor(""))
        assertEquals(FeatureGate.Tier.FREE, EntitlementPolicy.tierFor("bogus"))
        assertEquals(FeatureGate.Tier.PRO, EntitlementPolicy.tierFor("pro"))
        assertEquals(FeatureGate.Tier.PRO, EntitlementPolicy.tierFor(" PRO "))
        assertEquals(FeatureGate.Tier.CCOS, EntitlementPolicy.tierFor("studio"))
        assertEquals(FeatureGate.Tier.CCOS, EntitlementPolicy.tierFor("ccos"))
    }

    @Test
    fun editionLabelIsStable() {
        assertEquals("Pro", EntitlementPolicy.editionLabel("pro"))
        assertEquals("Studio", EntitlementPolicy.editionLabel("studio"))
        assertEquals("Studio", EntitlementPolicy.editionLabel("ccos"))
        assertEquals("Free", EntitlementPolicy.editionLabel(null))
        assertEquals("Free", EntitlementPolicy.editionLabel("nope"))
    }

    @Test
    fun appMajorParsesVersionName() {
        assertEquals(0L, EntitlementPolicy.appMajor("0.3.8-preview.1"))
        assertEquals(2L, EntitlementPolicy.appMajor("2.0.0"))
        assertEquals(0L, EntitlementPolicy.appMajor(null))
        assertEquals(0L, EntitlementPolicy.appMajor(""))
        assertEquals(0L, EntitlementPolicy.appMajor("x.y"))
    }

    @Test
    fun applyEntitlementOnlyOpensPaidTiers() {
        FeatureGate.setTierForDebug(FeatureGate.Tier.FREE)
        FeatureGate.applyEntitlement("pro")
        assertEquals(FeatureGate.Tier.PRO, FeatureGate.tier())
        assertTrue(FeatureGate.auditEnabled())

        FeatureGate.applyEntitlement("studio")
        assertEquals(FeatureGate.Tier.CCOS, FeatureGate.tier())

        // 无授权/坏 edition：回默认层级，Free 能力不回锁
        FeatureGate.applyEntitlement(null)
        assertEquals(FeatureGate.defaultTier(), FeatureGate.tier())
        assertTrue(FeatureGate.allows("import"))
        assertTrue(FeatureGate.allows("export.docx"))
    }
}
