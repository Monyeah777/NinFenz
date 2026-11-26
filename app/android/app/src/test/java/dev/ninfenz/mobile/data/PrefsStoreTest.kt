package dev.ninfenz.mobile.data

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class PrefsStoreTest {
    @get:Rule
    val tmp = TemporaryFolder()

    @Test
    fun defaultsPersistAndRevisionIncrements() {
        val store = PrefsStore(tmp.root)
        val first = store.load()
        assertEquals(0, first.revision)
        assertTrue(first.modules.enabled(Capability.CONTRACT))
        assertFalse(first.modules.enabled(Capability.NETWORK))

        val saved = store.save(first.copy(ui = first.ui.copy(fontScalePercent = 120)))
        assertEquals(1, saved.revision)
        val reloaded = PrefsStore(tmp.root).load()
        assertEquals(1, reloaded.revision)
        assertEquals(120, reloaded.ui.fontScalePercent)
    }

    @Test
    fun presetsModulesAndResetWork() {
        val store = PrefsStore(tmp.root)
        val minimal = store.applyWorkflow("minimal")
        assertFalse(minimal.modules.enabled(Capability.CONTRACT))
        assertFalse(minimal.modules.enabled(Capability.SEARCH))

        val reset = store.resetModule(Capability.CONTRACT)
        assertTrue(reset.modules.enabled(Capability.CONTRACT))
        assertEquals(2, reset.revision)

        val saved = store.saveWorkflow("我的预设")
        assertTrue(saved.workflows.any { it.source == "user" })
        assertTrue(saved.workflows.size <= 20)
    }

    @Test
    fun exportImportRoundTrips() {
        val store = PrefsStore(tmp.root)
        store.save(store.load().copy(ui = store.load().ui.copy(density = Density.COMPACT)))
        val exported = store.exportJson()

        val otherDir = tmp.newFolder("other")
        val other = PrefsStore(otherDir)
        val imported = other.importJson(exported)
        assertEquals(Density.COMPACT, imported.ui.density)
        assertEquals(1, imported.revision)
    }

    @Test
    fun invalidImportDoesNotOverwrite() {
        val store = PrefsStore(tmp.root)
        val before = store.save(store.load().copy(ui = store.load().ui.copy(fontScalePercent = 130)))
        val text = store.exportJson().replace(Regex("\"version\"\\s*:\\s*1"), "\"version\":2")
        val failed = runCatching { store.importJson(text) }
        assertTrue(failed.isFailure)
        assertEquals(before.revision, PrefsStore(tmp.root).load().revision)
    }

    @Test
    fun invalidFileFallsBackAndKeepsError() {
        val f = File(tmp.root, "nf-prefs.json")
        f.writeText("{not-json", Charsets.UTF_8)
        val store = PrefsStore(tmp.root)
        val fallback = store.load()
        assertEquals(0, fallback.revision)
        assertNotNull(store.lastError)
        assertTrue(f.readText(Charsets.UTF_8).startsWith("{not-json"))
    }

    @Test
    fun capabilityRegistryReflectsInstalledPrefs() {
        CapabilityRegistry.resetForTest()
        assertTrue(CapabilityRegistry.isEnabled(Capability.CONTRACT))
        assertFalse(CapabilityRegistry.isEnabled(Capability.NETWORK))
        CapabilityRegistry.install(NfPrefs(modules = ModuleToggles.allOff()))
        assertFalse(CapabilityRegistry.isEnabled(Capability.CONTRACT))
        CapabilityRegistry.resetForTest()
    }
}
