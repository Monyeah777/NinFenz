package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ProtocolSnapshotStoreTest {
    @Test
    fun savesRestoresAndRemoves() {
        val dir = Files.createTempDirectory("nf-psnap").toFile()
        val store = ProtocolSnapshotStore(dir, "p1")
        val list = store.save(mapOf("F1" to "a"), mapOf("C1" to true, "C2" to false))
        assertEquals(1, list.size)
        assertEquals("a", list.first().values["F1"])
        assertEquals(1, list.first().enabled.count { it.value })
        store.remove(list.first().id)
        assertTrue(store.list().isEmpty())
    }
}
