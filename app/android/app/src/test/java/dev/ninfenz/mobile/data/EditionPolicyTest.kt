package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.ui.shell.Detail
import dev.ninfenz.mobile.ui.shell.ShellState
import dev.ninfenz.mobile.ui.shell.TopDestination
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class EditionPolicyTest {
    @After
    fun resetTier() {
        FeatureGate.resetForTest()
        CapabilityRegistry.resetForTest()
    }

    @Test
    fun moduleOffBlocksModuleRoutes() {
        val modules = ModuleToggles.standard()
            .with(Capability.SEARCH, false)
            .with(Capability.MERGE, false)
        CapabilityRegistry.install(NfPrefs(modules = modules))
        assertFalse(EditionRoutePolicy.isAllowed(Detail.Search))
        assertFalse(EditionRoutePolicy.isAllowed(Detail.NfDocMerge))
        assertEquals(null, EditionRoutePolicy.sanitize(ShellState(TopDestination.LIBRARY, Detail.Search)).detail)
    }

    @Test
    fun dailySanitizesAuditRoutes() {
        FeatureGate.setTierForDebug(FeatureGate.Tier.FREE)
        val review = ShellState(TopDestination.LIBRARY, Detail.Review("p1"))
        assertEquals(Detail.Project("p1"), EditionRoutePolicy.sanitize(review).detail)
        val studio = ShellState(TopDestination.LIBRARY, Detail.PackBuilder("pack"))
        assertEquals(Detail.PackCenter, EditionRoutePolicy.sanitize(studio).detail)
        val ccos = ShellState(TopDestination.LIBRARY, Detail.Ccos)
        assertEquals(null, EditionRoutePolicy.sanitize(ccos).detail)
    }

    @Test
    fun proKeepsAuditRoutes() {
        FeatureGate.setTierForDebug(FeatureGate.Tier.PRO)
        val review = ShellState(TopDestination.LIBRARY, Detail.Review("p1"))
        assertEquals(review, EditionRoutePolicy.sanitize(review))
        assertTrue(EditionRoutePolicy.isAllowed(Detail.Ccos))
    }

    @Test
    fun dailyExportPolicyDisablesAuditGate() {
        FeatureGate.setTierForDebug(FeatureGate.Tier.FREE)
        val policy = ExportPolicy.current()
        assertFalse(policy.requireValidation)
        assertFalse(policy.verifyArtifacts)
        assertFalse(policy.allowPdfUa)
        assertFalse(policy.allowPreservation)
    }

    @Test
    fun proExportPolicyKeepsAuditGate() {
        FeatureGate.setTierForDebug(FeatureGate.Tier.PRO)
        val policy = ExportPolicy.current()
        assertTrue(policy.requireValidation)
        assertTrue(policy.verifyArtifacts)
        assertTrue(policy.allowPdfUa)
        assertTrue(policy.allowPreservation)
    }
}
