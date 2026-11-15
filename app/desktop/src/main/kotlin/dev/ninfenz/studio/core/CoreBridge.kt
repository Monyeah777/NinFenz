package dev.ninfenz.studio.core

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.intOrNull

data class CoreError(
    val code: String,
    val message: String,
    val fix: String,
    val path: String?,
    val exit: Int
)

/** CLI.md §2 信封；不变式 ok == (exit == 0)。FFI 面额外的顶层 op 字段被忽略。 */
data class CoreResponse(
    val ok: Boolean,
    val exit: Int,
    val result: JsonElement?,
    val error: CoreError?
) {
    fun resultObject(): JsonObject? = result as? JsonObject

    companion object {
        const val PROTOCOL_CODE = "NF-E-002"

        fun ok(result: JsonElement?): CoreResponse = CoreResponse(true, 0, result, null)

        fun failure(code: String, message: String, fix: String, exit: Int = 2, path: String? = null): CoreResponse =
            CoreResponse(false, exit, null, CoreError(code, message, fix, path, exit))

        fun fromEnvelope(text: String): CoreResponse {
            val root = try {
                Json.parseToJsonElement(text)
            } catch (t: Throwable) {
                return failure(PROTOCOL_CODE, "核心响应不是合法 JSON", "确认 nf_app_core.dll ABI 为 nf-app-core/1", 4)
            }
            val obj = root as? JsonObject
                ?: return failure(PROTOCOL_CODE, "核心响应不是 JSON 对象", "确认 nf_app_core.dll ABI 为 nf-app-core/1", 4)
            val okValue = (obj["ok"] as? JsonPrimitive)?.booleanOrNull
                ?: return failure(PROTOCOL_CODE, "核心响应缺 ok 字段", "确认 nf_app_core.dll ABI", 4)
            val exit = (obj["exit"] as? JsonPrimitive)?.intOrNull
                ?: return failure(PROTOCOL_CODE, "核心响应缺 exit 字段", "确认 nf_app_core.dll ABI", 4)
            if (okValue != (exit == 0)) {
                return failure(PROTOCOL_CODE, "信封自相矛盾：ok=" + okValue + " exit=" + exit,
                    "检查核心实现是否符合 CLI.md §2", 4)
            }
            if (okValue) return CoreResponse(true, 0, obj["result"], null)
            val eo = obj["error"] as? JsonObject
                ?: return failure(PROTOCOL_CODE, "失败响应缺 error 对象", "检查核心实现是否符合 CLI.md §2", 4)
            val code = textOf(eo, "code") ?: return failure(PROTOCOL_CODE, "error.code 缺失", "检查 CLI.md §2", 4)
            val message = textOf(eo, "message") ?: return failure(PROTOCOL_CODE, "error.message 缺失", "检查 CLI.md §2", 4)
            val fix = textOf(eo, "fix") ?: return failure(PROTOCOL_CODE, "error.fix 缺失", "检查 CLI.md §2", 4)
            return CoreResponse(false, exit, obj["result"], CoreError(code, message, fix, textOf(eo, "path"), exit))
        }

        private fun textOf(o: JsonObject, key: String): String? {
            val p = o[key] as? JsonPrimitive ?: return null
            return if (p.isString) p.content else null
        }
    }
}

interface CoreBridge {
    val backendName: String
    fun abiVersion(): String?
    /** 原生库不可用/未打包时的诊断说明（UI 展示 NF-E-005 指引）。 */
    fun loadDiagnostic(): String?
    suspend fun call(op: String, payload: JsonObject): CoreResponse
}

/** 原生库缺席：每次调用报 NF-E-005，绝不静默假数据。 */
class MissingCoreBridge(private val reason: String) : CoreBridge {
    override val backendName: String = "unavailable"
    override fun abiVersion(): String? = null
    override fun loadDiagnostic(): String = reason
    override suspend fun call(op: String, payload: JsonObject): CoreResponse = CoreResponse.failure(
        "NF-E-005",
        "共享核心不可用：" + reason,
        "先构建核心：cd app/core && cargo build --release，再重启 Studio（或把 nf_app_core.dll 放进 resources/native）",
        4
    )
}
