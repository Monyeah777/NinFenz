package dev.ninfenz.studio

import dev.ninfenz.studio.core.CoreBridgeJna
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test

/**
 * 真实 FFI 集成测试：加载 app/core/target/release/nf_app_core.dll（或 resources/native）。
 * DLL 不在场时 skip（不伪造通过）。
 */
class BridgeIntegrationTest {

    @Test
    fun loadsNativeDllAndReportsAbi() {
        val dll = CoreBridgeJna.locateDll()
        assumeTrue("nf_app_core.dll 不在场，跳过", dll != null)
        val bridge = CoreBridgeJna()
        assertEquals("nf-app-core/1", bridge.abiVersion())
    }

    @Test
    fun packagedDllResourceIsOnClasspath() {
        val stream = CoreBridgeJna::class.java.getResourceAsStream("/native/nf_app_core.dll")
        assumeTrue("native/nf_app_core.dll 资源不在场（未构建核心），跳过", stream != null)
        stream!!.use {
            val bytes = it.readBytes()
            assertTrue("打包的 dll 过小：" + bytes.size, bytes.size > 100_000)
            // MZ 头（Windows PE）
            assertEquals(0x4D, bytes[0].toInt())
            assertEquals(0x5A, bytes[1].toInt())
        }
    }

    @Test
    fun canonicalCallReturnsValidEnvelope() = runBlocking {
        val dll = CoreBridgeJna.locateDll()
        assumeTrue("nf_app_core.dll 不在场，跳过", dll != null)
        val bridge = CoreBridgeJna()
        val payload = buildJsonObject {
            put("value", buildJsonObject {
                put("b", 1)
                put("a", 2)
            })
        }
        val response = bridge.call("canonical", payload)
        // 契约级断言：要么成功，要么是带 code/message/fix 的规范错误信道
        assertTrue(response.ok || response.error != null)
        if (response.ok) {
            val result = response.resultObject()
            assertTrue(result != null)
            assertTrue(result!!.toString().contains("digest"))
        } else {
            assertTrue(response.error!!.code.startsWith("NF-"))
            assertTrue(response.error!!.fix.isNotBlank())
        }
    }
}
