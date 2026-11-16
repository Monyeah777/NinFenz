package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PackTrustStoreTest {
    @Test
    fun pinsAndClearsExactTree() {
        val dir = Files.createTempDirectory("nf-pack-trust").toFile()
        val store = PackTrustStore(dir)
        store.pin("pack", "1.0.0", "tree-a")
        assertTrue(store.isPinned("pack", "1.0.0", "tree-a"))
        assertFalse(store.isPinned("pack", "1.0.0", "tree-b"))
        assertEquals("tree-a", store.load()["pack@1.0.0"]?.tree)
        assertEquals("tree-a", store.pinnedTree("pack", "1.0.0"))
        store.clear("pack", "1.0.0")
        assertFalse(store.isPinned("pack", "1.0.0", "tree-a"))
    }

    @Test
    fun corruptFileIsEmpty() {
        val dir = Files.createTempDirectory("nf-pack-trust-2").toFile()
        java.io.File(dir, "pack-trust.json").writeText("{bad")
        assertTrue(PackTrustStore(dir).load().isEmpty())
    }
}
