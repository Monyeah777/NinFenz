package dev.ninfenz.mobile.data

import java.nio.file.Files
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SavedViewStoreTest {
    @Test
    fun savesReplacesAndRemovesNamedView() {
        val dir = Files.createTempDirectory("nf-views").toFile()
        val store = SavedViewStore(dir)
        store.save(SavedViewStore.View("v1", "未交付", "assembled", "RECENT", false, null))
        store.save(SavedViewStore.View("v2", "客户", "exported", "TITLE", false, "客户"))
        assertEquals(2, store.load().size)
        store.save(SavedViewStore.View("v1", "未交付", "draft", "RECENT", true, null))
        assertEquals(2, store.load().size)
        assertEquals("draft", store.load().first { it.name == "未交付" }.status)
        store.remove("v1")
        assertEquals(1, store.load().size)
    }

    @Test
    fun extensionViewIsReadOnly() {
        val dir = Files.createTempDirectory("nf-views-ext").toFile()
        val view = SavedViewStore(dir).fromExtension("recent", buildJsonObject {
            put("name", "最近")
            put("status", "assembled")
            put("favorites_only", true)
        })
        assertTrue(view != null && view.readOnly)
    }
}
