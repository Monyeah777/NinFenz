package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ExtensionTrustStoreTest {
    @Test
    fun pinsDigestAndRevokes() {
        val dir = Files.createTempDirectory("nf-trust").toFile()
        val store = ExtensionTrustStore(dir)
        assertFalse(store.isTrusted("a", "d1"))
        store.trust("a", "d1")
        assertTrue(store.isTrusted("a", "d1"))
        assertFalse(store.isTrusted("a", "d2"))
        store.revoke("a")
        assertFalse(store.isTrusted("a", "d1"))
    }
}
