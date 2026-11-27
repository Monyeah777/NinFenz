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
        "assemble" -> {
            val raw = plan
            val specJson = spec
            if (raw == null || specJson == null) {
                Result.failure(IllegalStateException(context.getString(dev.ninfenz.mobile.R.string.delivery_macro_missing_plan_spec)))
            } else {
                val response = call("assemble", buildJsonObject {
                    put("plan", raw)
                    put("spec", specJson)
                    put("inputs", buildJsonObject { inputs.forEach { (key, value) -> put(key, value) } })
                })
                val md = response.resultObject()?.let { J.optString(it, "markdown") }
                if (response.ok && !md.isNullOrBlank()) {
                    onMarkdown(md)
                    Result.success("assembled")
                } else {
                    Result.failure(IllegalStateException(response.error?.message ?: "assemble failed"))
                }
            }
        }
        "validate" -> {
            val md = markdownProvider()
            val specJson = spec
            val raw = plan
            if (md.isNullOrBlank() || specJson == null || raw == null) {
                Result.failure(IllegalStateException(context.getString(dev.ninfenz.mobile.R.string.delivery_macro_missing_inputs)))
            } else {
                val response = call("validate", buildJsonObject {
                    put("markdown", md)
                    put("spec", specJson)
                    put("plan", raw)
                    put("level", "L1")
                })
                if (response.ok) Result.success("validated")
                else Result.failure(IllegalStateException(response.error?.message ?: "validate failed"))
            }
        }
        "import" -> {
            val file = params["file"]?.jsonPrimitive?.content
            if (file.isNullOrBlank()) {
                Result.failure(IllegalStateException(context.getString(dev.ninfenz.mobile.R.string.delivery_macro_import_missing_file)))
            } else {
                val response = call("import", buildJsonObject { put("file", file) })
                if (response.ok) Result.success("imported")
                else Result.failure(IllegalStateException(response.error?.message ?: "import failed"))
            }
        }
        "map" -> {
            val raw = ImportDraftStore(context.filesDir).load()
            if (raw.isNullOrBlank()) {
                Result.failure(IllegalStateException(context.getString(dev.ninfenz.mobile.R.string.delivery_macro_no_import_draft)))
            } else {
                val input = runCatching { Json.parseToJsonElement(raw).jsonObject }.orNullLogged("DeliveryMacroExecutor")
                if (input == null) {
                    Result.failure(IllegalStateException(context.getString(dev.ninfenz.mobile.R.string.delivery_macro_draft_not_json)))
                } else {
                    val response = call("map-suggest", buildJsonObject { put("import", input) })
                    if (response.ok) Result.success("mapped")
                    else Result.failure(IllegalStateException(response.error?.message ?: "map failed"))
                }
            }
        }
        "export" -> {
            val md = markdownProvider()
            val blocked = ContractGate.blocked(ContractIrStore(context.filesDir, projectId).loadSolve())
            when {
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
        else -> Result.failure(
            IllegalStateException(context.getString(dev.ninfenz.mobile.R.string.delivery_macro_unwired, action))
        )
    }
}
