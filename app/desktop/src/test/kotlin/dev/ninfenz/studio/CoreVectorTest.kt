package dev.ninfenz.studio

import dev.ninfenz.studio.core.CoreBridgeJna
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Desktop JNA 与 CLI/Python 共享的 canonical golden。 */
class CoreVectorTest {
    @Test
    fun canonicalMatchesSharedGolden() = runBlocking {
        val response = CoreBridgeJna().call(
            "canonical",
            buildJsonObject {
                put("value", buildJsonObject {
                    put("b", 1)
                    put("a", 2)
                })
            }
        )
        assertTrue(response.error?.message ?: "", response.ok)
        val result = response.resultObject()!!
        assertEquals("{\"a\":2,\"b\":1}", result["canonical"]?.jsonPrimitive?.content)
        assertEquals(
            "d3626ac30a87e6f7a6428233b3c68299976865fa5508e4267c5415c76af7a772",
            result["digest"]?.jsonPrimitive?.content
        )
    }
}
