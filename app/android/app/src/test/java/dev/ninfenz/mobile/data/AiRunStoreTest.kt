package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.CcosResult
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

    @Test
    fun mapsCcosResultStatusToRunAndTasks() {
        val store = AiRunStore(tmp.root)
        val run = buildJsonObject {
            put("schema", "nf-ai-run/1")
            put("id", "run-2")
            put("project_id", "p1")
            put("status", "queued")
            put("tasks", buildJsonArray {
                add(buildJsonObject { put("id", "T01"); put("title", "A"); put("status", "planned") })
            })
        }
        val result = CcosResult(
            taskId = "t1",
            taskDigest = "a".repeat(64),
            status = "partial",
            artifacts = emptyList(),
            evidence = emptyList(),
            reportSummary = "",
            issues = emptyList(),
            reviewRequired = true,
            reviewState = "pending",
            reviewer = null,
            note = null,
            engine = "test",
            startedAt = "",
            finishedAt = "",
            model = "m1"
        )
        val mapped = store.applyResult(run, result)
        assertEquals("partial", mapped["status"]?.toString()?.trim('"'))
        assertEquals("m1", mapped["model"]?.toString()?.trim('"'))
        assertTrue(mapped["tasks"]?.toString()?.contains("partial") == true)
    }
}
