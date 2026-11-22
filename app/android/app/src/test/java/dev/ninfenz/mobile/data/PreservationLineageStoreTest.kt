package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PreservationLineageStoreTest {
    @Test
    fun savesAndLoads() {
        val dir = Files.createTempDirectory("lineage").toFile()
        val store = PreservationLineageStore(dir)
        assertNull(store.load("p1"))
        store.save("p1", "a".repeat(64))
        assertEquals("a".repeat(64), store.load("p1"))
    }
}
