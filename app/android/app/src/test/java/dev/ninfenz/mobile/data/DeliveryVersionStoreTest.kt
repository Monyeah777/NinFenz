package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Test

class DeliveryVersionStoreTest {
    @Test
    fun savesNewestFirstAndSkipsDuplicate() {
        val dir = Files.createTempDirectory("nf-version").toFile()
        val store = DeliveryVersionStore(dir)
        store.save("p1", "v1")
        store.save("p1", "v1")
        store.save("p1", "v2")
        val versions = store.load("p1")
        assertEquals(2, versions.size)
        assertEquals("v2", versions.first().markdown)
        assertEquals("v1", versions.last().markdown)
    }

    @Test
    fun capsAtTwenty() {
        val dir = Files.createTempDirectory("nf-version-cap").toFile()
        val store = DeliveryVersionStore(dir)
        repeat(25) { store.save("p1", "v$it") }
        assertEquals(20, store.load("p1").size)
    }
}
