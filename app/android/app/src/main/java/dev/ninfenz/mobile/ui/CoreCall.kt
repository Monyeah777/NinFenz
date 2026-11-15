package dev.ninfenz.mobile.ui

import dev.ninfenz.mobile.core.Core
import dev.ninfenz.mobile.core.CoreResponse
import kotlinx.serialization.json.JsonObject

/** 统一桥调用：异常也收敛成 NF-E-005 响应，UI 只有一条错误渲染路径（不静默吞错）。 */
suspend fun safeCall(op: String, payload: JsonObject): CoreResponse = try {
    Core.bridge.call(op, payload)
} catch (t: Throwable) {
    CoreResponse.failure(
        "NF-E-005",
        "核心调用异常：" + (t.message ?: t.javaClass.simpleName),
        "检查原生库 ABI 与架构；诊断见设置页",
        4
    )
}
