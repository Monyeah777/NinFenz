package dev.ninfenz.mobile.core

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.intOrNull

/** 核心错误（CLI.md §2）：code/message/fix 必带；path 可选（RFC 6901）。 */
data class CoreError(
    val code: String,
    val message: String,
    val fix: String,
    val path: String?,
    val exit: Int
)

/**
 * CLI.md §2 响应信封。不变式：ok == (exit == 0)；
 * ok=false 时 error 必带 code/message/fix；ok=true 时 exit 必为 0。
 */
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

        /** 解析核心吐出的信封；任何自相矛盾一律收敛为 NF-E-002（fail-closed，不猜）。 */
        fun fromEnvelope(text: String): CoreResponse {
            val root = try {
                Json.parseToJsonElement(text)
            } catch (t: Throwable) {
                return failure(PROTOCOL_CODE, "核心响应不是合法 JSON", "确认原生库 ABI 版本为 nf-app-core/1；重装 libnf_app_core.so", 4)
            }
            val obj = root as? JsonObject
                ?: return failure(PROTOCOL_CODE, "核心响应不是 JSON 对象", "确认原生库 ABI 版本为 nf-app-core/1", 4)
            val okValue = (obj["ok"] as? JsonPrimitive)?.booleanOrNull
                ?: return failure(PROTOCOL_CODE, "核心响应缺 ok 布尔字段", "确认原生库 ABI 版本为 nf-app-core/1", 4)
            val exit = (obj["exit"] as? JsonPrimitive)?.intOrNull
                ?: return failure(PROTOCOL_CODE, "核心响应缺 exit 整数字段", "确认原生库 ABI 版本为 nf-app-core/1", 4)

            if (okValue != (exit == 0)) {
                return failure(
                    PROTOCOL_CODE,
                    "核心响应信封自相矛盾：ok=" + okValue + " exit=" + exit,
                    "检查原生库实现是否遵循 app/docs/CLI.md §2", 4
                )
            }
            if (okValue) {
                return CoreResponse(true, 0, obj["result"], null)
            }
            val eo = obj["error"] as? JsonObject
                ?: return failure(PROTOCOL_CODE, "核心失败响应缺 error 对象", "检查原生库实现是否遵循 CLI.md §2", 4)
            val code = textOf(eo, "code")
                ?: return failure(PROTOCOL_CODE, "error.code 缺失", "检查原生库实现是否遵循 CLI.md §2", 4)
            val message = textOf(eo, "message")
                ?: return failure(PROTOCOL_CODE, "error.message 缺失", "检查原生库实现是否遵循 CLI.md §2", 4)
            val fix = textOf(eo, "fix")
                ?: return failure(PROTOCOL_CODE, "error.fix 缺失", "检查原生库实现是否遵循 CLI.md §2", 4)
            val path = textOf(eo, "path")
            return CoreResponse(false, exit, obj["result"], CoreError(code, message, fix, path, exit))
        }

        private fun textOf(o: JsonObject, key: String): String? {
            val p = o[key] as? JsonPrimitive ?: return null
            return if (p.isString) p.content else null
        }
    }
}

/** 三端共享核心桥（CLI.md §5：JSON over C ABI，一 op 一调用）。 */
interface CoreBridge {
    val backendName: String
    /** 原生库 ABI（如 nf-app-core/1）；不可用时 null（不伪装）。 */
    fun abiVersion(): String?
    suspend fun call(op: String, payload: JsonObject): CoreResponse
}

/** 原生库缺席时的桥：每次调用明确报 NF-E-005，绝不静默返回假结果。 */
class MissingCoreBridge(
    private val reason: String,
    private val guidance: String
) : CoreBridge {
    override val backendName: String = "unavailable"
    override fun abiVersion(): String? = null
    override suspend fun call(op: String, payload: JsonObject): CoreResponse =
        CoreResponse.failure("NF-E-005", "共享核心不可用：" + reason, guidance, 4)
}
