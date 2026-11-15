package dev.ninfenz.mobile

import dev.ninfenz.mobile.core.CoreBridge
import dev.ninfenz.mobile.core.CoreResponse
import kotlinx.serialization.json.JsonObject

/** 测试专用桥：只回放显式入队的响应，不产生任何「看起来像核心」的默认数据。 */
class FakeCoreBridge(
    private val queued: MutableList<CoreResponse> = mutableListOf()
) : CoreBridge {

    val calls: MutableList<Pair<String, JsonObject>> = mutableListOf()
    private var abi: String? = "fake-abi/1"

    override val backendName: String = "fake-test"

    override fun abiVersion(): String? = abi

    fun setAbi(value: String?) {
        abi = value
    }

    fun enqueue(response: CoreResponse): FakeCoreBridge {
        queued.add(response)
        return this
    }

    override suspend fun call(op: String, payload: JsonObject): CoreResponse {
        calls.add(op to payload)
        if (queued.isEmpty()) {
            return CoreResponse.failure("NF-E-005", "fake bridge 无待回放响应", "测试里先 enqueue", 4)
        }
        return queued.removeAt(0)
    }
}
