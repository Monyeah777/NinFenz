package dev.ninfenz.mobile.data

import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class AiRunStoreTest {
    @get:Rule
    val tmp = TemporaryFolder()

    @Test
    fun savesListsAndDeletes() {
        val store = AiRunStore(tmp.root)
        val run = buildJsonObject {
            put("schema", "nf-ai-run/1")
            put("id", "run-1")
            put("project_id", "p1")
            put("status", "queued")
            put("tasks", buildJsonArray {
                add(buildJsonObject { put("id", "T01"); put("title", "A"); put("status", "planned") })
                add(buildJsonObject { put("id", "T02"); put("title", "B"); put("status", "planned") })
            })
        }
        store.save(run)
        assertEquals(1, store.list().size)
        assertEquals(2, store.list().first().tasks)
        store.delete("run-1")
        assertTrue(store.list().isEmpty())
    }
}
