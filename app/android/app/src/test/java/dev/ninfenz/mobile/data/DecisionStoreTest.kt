package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DecisionStoreTest {
    @Test
    fun appendReversePersist() {
        val dir = Files.createTempDirectory("nf-decision").toFile()
        val store = DecisionStore(dir)
        val r = store.append("sdir-repair", "heading jump", undoable = true)
        assertEquals(1, store.load().size)
        assertTrue(store.reverse(r.id))
        assertTrue(store.load().single().reversed)
    }

    @Test
    fun missingFileIsEmpty() {
        val dir = Files.createTempDirectory("nf-decision-empty").toFile()
        assertTrue(DecisionStore(dir).load().isEmpty())
    }
}
