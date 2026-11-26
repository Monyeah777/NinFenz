package dev.ninfenz.mobile.model

import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MacroRunnerTest {
    private fun plan(): kotlinx.serialization.json.JsonObject = buildJsonObject {
        put("steps", buildJsonArray {
            listOf("S01", "S02", "S03").forEach { id ->
                add(buildJsonObject {
                    put("id", id)
                    put("action", "validate")
                    put("params", buildJsonObject {})
                })
            }
        })
    }

    @Test
    fun isolatesFailedStepAndContinues() {
        val seen = mutableListOf<String>()
        val result = runBlocking {
            MacroRunner.run(plan()) { _, _ ->
                seen += "step"
                if (seen.size == 2) Result.failure(IllegalStateException("boom")) else Result.success("ok")
            }
        }
        assertEquals("partial", result.status)
        assertEquals(3, result.steps.size)
        assertEquals(1, result.failures)
        assertEquals("failed", result.steps[1].status)
        assertEquals("done", result.steps[2].status)
        assertEquals(3, seen.size)
    }

    @Test
    fun allFailedIsFailed() {
        val result = runBlocking {
            MacroRunner.run(plan()) { _, _ -> Result.failure(IllegalStateException("x")) }
        }
        assertEquals("failed", result.status)
        assertEquals(3, result.failures)
    }
}
