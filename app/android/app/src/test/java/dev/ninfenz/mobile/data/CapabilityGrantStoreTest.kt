package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class CapabilityGrantStoreTest {
    @Test
    fun savesAndLoads() {
        val dir = Files.createTempDirectory("grant").toFile()
        val store = CapabilityGrantStore(dir)
        assertNull(store.load("p1"))
        store.save("p1", CapabilityGrant(setOf(CapabilityGrant.READ), 999))
        assertEquals(setOf(CapabilityGrant.READ), store.load("p1")?.caps)
        assertEquals(999L, store.load("p1")?.expiresAt)
    }
}
