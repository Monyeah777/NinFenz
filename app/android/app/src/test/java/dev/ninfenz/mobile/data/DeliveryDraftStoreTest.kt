package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

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
    fun savesAndLoadsPlan() {
        val dir = Files.createTempDirectory("nf-delivery-plan").toFile()
        val store = DeliveryDraftStore(dir)
        val plan = buildJsonObject { put("steps", 3); put("slots", 2) }
        store.save("p", mapOf("SLT-01" to "alpha"), plan)
        assertEquals("alpha", store.load("p")["SLT-01"])
        assertEquals(3, store.loadPlan("p")?.get("steps")?.toString()?.toIntOrNull())
    }

    @Test
    fun savesAndLoadsMarkdown() {
        val dir = Files.createTempDirectory("nf-delivery-md").toFile()
        val store = DeliveryDraftStore(dir)
        store.save("p", mapOf("SLT-01" to "alpha"), null, "# 标题\n\n正文")
        assertEquals("# 标题\n\n正文", store.loadMarkdown("p"))
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
