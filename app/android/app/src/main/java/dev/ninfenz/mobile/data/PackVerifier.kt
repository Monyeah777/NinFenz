package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.core.Core
import dev.ninfenz.mobile.core.CoreBridge
import dev.ninfenz.mobile.core.CoreResponse
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** Pack 校验：core pack-verify（root=已安装目录）；失败返回错误码，不伪造通过。 */
class PackVerifier(private val injectedBridge: CoreBridge? = null) {
    private fun bridge(): CoreBridge? = injectedBridge ?: runCatching { Core.bridge }.getOrNull()

    suspend fun verify(pack: PackEntry): CoreResponse = withContext(Dispatchers.IO) {
        val core = bridge()
            ?: return@withContext CoreResponse.failure(
                "NF-E-005",
                "原生核心不可用，无法校验 Pack",
                "重装原生库并运行诊断；校验需要 core pack-verify",
                4
            )
        try {
            core.call("pack-verify", buildJsonObject { put("root", pack.dir.absolutePath) })
        } catch (t: Throwable) {
            CoreResponse.failure(
                "NF-E-005",
                "校验调用异常：" + (t.message ?: t.javaClass.simpleName),
                "检查核心桥与 Pack 目录；诊断见设置页",
                4
            )
        }
    }
}
