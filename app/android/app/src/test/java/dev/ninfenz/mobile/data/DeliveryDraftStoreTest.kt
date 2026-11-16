package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DeliveryDraftStoreTest {
    @Test
    fun savesAndLoadsNonBlankSlots() {
        val dir = Files.createTempDirectory("nf-delivery-draft").toFile()
        val store = DeliveryDraftStore(dir)
        store.save("p/1", mapOf("SLT-01" to "alpha", "SLT-02" to " ", "SLT-03" to "gamma"))
        val loaded = store.load("p/1")
        assertEquals("alpha", loaded["SLT-01"])
        assertEquals("gamma", loaded["SLT-03"])
        assertTrue(!loaded.containsKey("SLT-02"))
    }

    @Test
    fun emptySlotsDeleteDraftAndCorruptFileIsIgnored() {
        val dir = Files.createTempDirectory("nf-delivery-draft-2").toFile()
        val store = DeliveryDraftStore(dir)
        store.save("p", mapOf("SLT-01" to "x"))
        store.save("p", mapOf("SLT-01" to ""))
        assertTrue(store.load("p").isEmpty())

        val bad = java.io.File(dir, "drafts/delivery-p.json")
        bad.parentFile?.mkdirs()
        bad.writeText("{not-json", Charsets.UTF_8)
        assertTrue(store.load("p").isEmpty())
    }
}
