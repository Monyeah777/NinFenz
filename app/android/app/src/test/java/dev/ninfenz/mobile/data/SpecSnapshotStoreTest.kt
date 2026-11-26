package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.MdSpec
import dev.ninfenz.mobile.model.SpecSection
import dev.ninfenz.mobile.model.SpecSlot
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SpecSnapshotStoreTest {
    @Test
    fun savesRestoresAndRemoves() {
        val dir = Files.createTempDirectory("nf-snap").toFile()
        val store = SpecSnapshotStore(dir, "p1")
        val spec = MdSpec("spec", "标题", "1", 1, listOf(SpecSection("S1", "章", 1, true, listOf("SL1"))), listOf(SpecSlot("SL1", "槽", "S1", "text", true)))
        assertEquals(1, store.save(spec).size)
        val snap = store.list().first()
        assertEquals(1, snap.sections)
        val restored = store.restore(snap)
        assertEquals("S1", restored.sections.first().id)
        store.remove(snap.id)
        assertTrue(store.list().isEmpty())
    }
}
