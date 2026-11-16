package dev.ninfenz.mobile.ui

import android.content.Context
import dev.ninfenz.mobile.R
import dev.ninfenz.mobile.core.Core
import dev.ninfenz.mobile.core.CoreResponse
import kotlinx.serialization.json.JsonObject

@Volatile
private var appContext: Context? = null

/** 只保存 applicationContext，供异常文案取资源；不持有 Activity。 */
fun installCoreCallContext(context: Context) {
    appContext = context.applicationContext
}

/** 统一桥调用：异常也收敛成 NF-E-005 响应，UI 只有一条错误渲染路径（不静默吞错）。 */
suspend fun safeCall(op: String, payload: JsonObject): CoreResponse = try {
    Core.bridge.call(op, payload)
} catch (t: Throwable) {
    val detail = t.message ?: t.javaClass.simpleName
    val ctx = appContext
    CoreResponse.failure(
        "NF-E-005",
        ctx?.getString(R.string.core_call_failed, detail) ?: "核心调用异常：$detail",
        ctx?.getString(R.string.core_call_failed_fix) ?: "检查原生库 ABI 与架构；诊断见设置页",
        4
    )
}
