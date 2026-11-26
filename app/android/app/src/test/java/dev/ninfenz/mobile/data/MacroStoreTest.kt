package dev.ninfenz.mobile.data

import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class MacroStoreTest {
    @get:Rule
    val tmp = TemporaryFolder()

    @Test
    fun savesListsAndDeletes() {
        val store = MacroStore(tmp.root)
        val macro = buildJsonObject {
            put("schema", "nf-macro/1")
            put("id", "demo")
            put("title", "Demo")
            put("digest", "a".repeat(64))
            put("steps", buildJsonArray {
                add(buildJsonObject { put("id", "S01"); put("action", "import"); put("params", buildJsonObject {}) })
                add(buildJsonObject { put("id", "S02"); put("action", "export"); put("params", buildJsonObject {}) })
            })
        }
        store.save(macro)
        assertEquals(1, store.list().size)
        assertEquals(2, store.list().first().steps)
        store.delete("demo")
        assertTrue(store.list().isEmpty())
    }
}
