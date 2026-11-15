package dev.ninfenz.studio.ui

import dev.ninfenz.studio.core.Core
import dev.ninfenz.studio.core.CoreResponse
import kotlinx.serialization.json.JsonObject

/** 统一桥调用：异常也收敛成 NF-E-005，UI 只有一条错误渲染路径。 */
suspend fun safeCall(op: String, payload: JsonObject): CoreResponse = try {
    Core.bridge.call(op, payload)
} catch (t: Throwable) {
    CoreResponse.failure("NF-E-005", "核心调用异常：" + (t.message ?: t.javaClass.simpleName),
        "检查 nf_app_core.dll 与 ABI", 4)
}
