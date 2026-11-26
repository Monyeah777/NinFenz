package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ExtensionTrustStoreTest {
    private val d1 = "a".repeat(64)
    private val d2 = "b".repeat(64)

    @Test
    fun pinsDigestAndRevokes() {
        val dir = Files.createTempDirectory("nf-trust").toFile()
        val store = ExtensionTrustStore(dir)
        assertFalse(store.isTrusted("a", d1))
        store.trust("a", d1, "f".repeat(64))
        assertTrue(store.isTrusted("a", d1))
        assertFalse(store.isTrusted("a", d2))
        assertEquals("f".repeat(64), store.entry("a")?.fingerprint)
        store.revoke("a")
        assertFalse(store.isTrusted("a", d1))
    }

    @Test
    fun exportImportRoundTrips() {
        val dir = Files.createTempDirectory("nf-trust").toFile()
        val store = ExtensionTrustStore(dir)
        store.trust("a", d1, "f".repeat(64), "test")
        val json = store.exportJson()
        val other = ExtensionTrustStore(Files.createTempDirectory("nf-trust2").toFile())
        val imported = other.importJson(json)
        assertEquals(1, imported.size)
        assertTrue(other.isTrusted("a", d1))
        assertEquals("test", other.entry("a")?.note)
    }

    @Test
    fun legacyTrustedMapStillReads() {
        val dir = Files.createTempDirectory("nf-trust3").toFile()
        File(dir, "extension-trust.json").writeText(
            "{\"trusted\":{\"a\":\"" + d1 + "\"}}",
            Charsets.UTF_8
        )
        val store = ExtensionTrustStore(dir)
        assertTrue(store.isTrusted("a", d1))
    }
}
