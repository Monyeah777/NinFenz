package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.util.orNullLogged
import android.content.Context
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.ContractGate
import dev.ninfenz.mobile.data.ContractIrStore
import dev.ninfenz.mobile.data.ImportDraftStore
import dev.ninfenz.mobile.ui.safeCall
import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** Delivery 宏动作执行器：单宏与批量共用，export 仍受合同 gate。 */
class DeliveryMacroExecutor(
    private val context: Context,
    private val projectId: String,
    private val spec: JsonObject?,
    private val plan: JsonObject?,
    private val inputs: Map<String, String>,
    private val markdownProvider: () -> String?,
    private val onMarkdown: (String) -> Unit,
    private val call: suspend (String, JsonObject) -> CoreResponse = { op, payload -> safeCall(op, payload) }
) {
    suspend fun run(action: String, params: JsonObject): Result<String> = when (action) {
        "assemble" -> assemble()
        "validate" -> validateDoc()
        "import" -> importFile(params)
        "map" -> mapDraft()
        "export" -> exportDoc()
        else -> Result.failure(
            IllegalStateException(context.getString(dev.ninfenz.mobile.R.string.delivery_macro_unwired, action))
        )
    }

    private suspend fun assemble(): Result<String> {
        val raw = plan
        val specJson = spec
        if (raw == null || specJson == null) {
            return Result.failure(IllegalStateException(context.getString(dev.ninfenz.mobile.R.string.delivery_macro_missing_plan_spec)))
        }
        val response = call("assemble", buildJsonObject {
            put("plan", raw)
            put("spec", specJson)
            put("inputs", buildJsonObject { inputs.forEach { (key, value) -> put(key, value) } })
        })
        val md = response.resultObject()?.let { J.optString(it, "markdown") }
        if (response.ok && !md.isNullOrBlank()) {
            onMarkdown(md)
            return Result.success("assembled")
        }
        return Result.failure(IllegalStateException(response.error?.message ?: "assemble failed"))
    }

    private suspend fun validateDoc(): Result<String> {
        val md = markdownProvider()
        val specJson = spec
        val raw = plan
        if (md.isNullOrBlank() || specJson == null || raw == null) {
            return Result.failure(IllegalStateException(context.getString(dev.ninfenz.mobile.R.string.delivery_macro_missing_inputs)))
        }
        val response = call("validate", buildJsonObject {
            put("markdown", md)
            put("spec", specJson)
            put("plan", raw)
            put("level", "L1")
        })
        return if (response.ok) Result.success("validated")
        else Result.failure(IllegalStateException(response.error?.message ?: "validate failed"))
    }

    private suspend fun importFile(params: JsonObject): Result<String> {
        val file = params["file"]?.jsonPrimitive?.content
        if (file.isNullOrBlank()) {
            return Result.failure(IllegalStateException(context.getString(dev.ninfenz.mobile.R.string.delivery_macro_import_missing_file)))
        }
        val response = call("import", buildJsonObject { put("file", file) })
        return if (response.ok) Result.success("imported")
        else Result.failure(IllegalStateException(response.error?.message ?: "import failed"))
    }

    private suspend fun mapDraft(): Result<String> {
        val raw = ImportDraftStore(context.filesDir).load()
        if (raw.isNullOrBlank()) {
            return Result.failure(IllegalStateException(context.getString(dev.ninfenz.mobile.R.string.delivery_macro_no_import_draft)))
        }
        val input = runCatching { Json.parseToJsonElement(raw).jsonObject }.orNullLogged("DeliveryMacroExecutor")
        if (input == null) {
            return Result.failure(IllegalStateException(context.getString(dev.ninfenz.mobile.R.string.delivery_macro_draft_not_json)))
        }
        val response = call("map-suggest", buildJsonObject { put("import", input) })
        return if (response.ok) Result.success("mapped")
        else Result.failure(IllegalStateException(response.error?.message ?: "map failed"))
    }

    private fun exportDoc(): Result<String> {
        val md = markdownProvider()
        val blocked = ContractGate.blocked(ContractIrStore(context.filesDir, projectId).loadSolve())
        return when {
            blocked -> Result.failure(IllegalStateException(context.getString(dev.ninfenz.mobile.R.string.delivery_contract_unsat)))
            md.isNullOrBlank() -> Result.failure(IllegalStateException(context.getString(dev.ninfenz.mobile.R.string.delivery_macro_missing_markdown)))
            else -> {
                val dir = File(File(context.filesDir, "exports"), "macro").apply { mkdirs() }
                val file = File(dir, "macro-" + System.currentTimeMillis() + ".md")
                file.writeText(md, Charsets.UTF_8)
                Result.success(file.name)
            }
        }
    }
}
