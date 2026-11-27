package dev.ninfenz.mobile.ui.screens

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.data.ContractIrStore
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class DeliveryMacroExecutorTest {
    private val context: Context = ApplicationProvider.getApplicationContext()

    private fun executor(
        projectId: String,
        markdown: () -> String? = { null },
        onMarkdown: (String) -> Unit = {},
        call: suspend (String, JsonObject) -> CoreResponse = { _, _ -> CoreResponse.ok(buildJsonObject {}) }
    ): DeliveryMacroExecutor = DeliveryMacroExecutor(
        context = context,
        projectId = projectId,
        spec = buildJsonObject { put("id", "spec") },
        plan = buildJsonObject { put("id", "plan") },
        inputs = mapOf("SLT-01" to "x"),
        markdownProvider = markdown,
        onMarkdown = onMarkdown,
        call = call
    )

    @Test
    fun exportBlockedWhenContractUnsatisfiable() = kotlinx.coroutines.runBlocking {
        val store = ContractIrStore(context.filesDir, "gate-p1")
        store.saveSolve(buildJsonObject { put("satisfiable", false) })
        val result = executor("gate-p1", markdown = { "hello" }).run("export", buildJsonObject {})
        assertTrue(result.isFailure)
        assertFalse(java.io.File(context.filesDir, "exports/macro").listFiles().orEmpty().any { it.name.contains("gate") })
    }

    @Test
    fun assembleUpdatesMarkdown() = kotlinx.coroutines.runBlocking {
        var updated: String? = null
        val result = executor(
            projectId = "asm-p1",
            onMarkdown = { updated = it },
            call = { _, _ -> CoreResponse.ok(buildJsonObject { put("markdown", "# hi") }) }
        ).run("assemble", buildJsonObject {})
        assertEquals("assembled", result.getOrNull())
        assertEquals("# hi", updated)
    }

    @Test
    fun unknownActionFails() = kotlinx.coroutines.runBlocking {
        assertTrue(executor("unknown-p1").run("nope", buildJsonObject {}).isFailure)
    }
}
