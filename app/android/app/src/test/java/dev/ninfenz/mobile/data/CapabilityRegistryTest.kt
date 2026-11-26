package dev.ninfenz.mobile.data

import org.junit.Assert.assertEquals
import org.junit.After
import org.junit.Test

class CapabilityRegistryTest {
    @After
    fun tearDown() {
        CapabilityRegistry.resetForTest()
    }

    @Test
    fun observerFiresOnInstallAndStopsAfterRemove() {
        var count = 0
        val remove = CapabilityRegistry.observe { count++ }
        CapabilityRegistry.install(NfPrefs(modules = ModuleToggles.allOff()))
        assertEquals(1, count)
        remove()
        CapabilityRegistry.install(NfPrefs(modules = ModuleToggles.allOn()))
        assertEquals(1, count)
    }
}
