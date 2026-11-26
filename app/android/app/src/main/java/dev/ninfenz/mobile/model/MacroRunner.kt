package dev.ninfenz.mobile.model

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject

/** 语义宏执行器：逐步执行，单步失败只隔离该步；不做坐标点击。 */
data class MacroStepResult(
    val id: String,
    val action: String,
    val status: String,
    val message: String = ""
)

data class MacroRunResult(
    val status: String,
    val steps: List<MacroStepResult>,
    val failures: Int
)

object MacroRunner {
    fun run(
        plan: JsonObject,
        handler: (action: String, params: JsonObject) -> Result<String>
    ): MacroRunResult {
        val steps = plan["steps"]?.jsonArray.orEmpty()
        val results = mutableListOf<MacroStepResult>()
        var failures = 0
        for (element in steps) {
            if (element !is JsonObject) {
                failures += 1
                results += MacroStepResult("?", "?", "failed", "步骤不是对象")
                continue
            }
            val step = element
            val id = step["id"]?.toString()?.trim('"').orEmpty()
            val action = step["action"]?.toString()?.trim('"').orEmpty()
            val params = step["params"] as? JsonObject ?: JsonObject(emptyMap())
            val outcome = runCatching { handler(action, params) }
            val success = outcome.getOrNull()?.isSuccess == true
            if (success) {
                results += MacroStepResult(id, action, "done", outcome.getOrNull()?.getOrNull().orEmpty())
            } else {
                failures += 1
                val message = outcome.exceptionOrNull()?.message
                    ?: outcome.getOrNull()?.exceptionOrNull()?.message
                    ?: "步骤失败"
                results += MacroStepResult(id, action, "failed", message)
            }
        }
        val status = when {
            failures == 0 -> "done"
            failures == results.size -> "failed"
            else -> "partial"
        }
        return MacroRunResult(status, results, failures)
    }
}
