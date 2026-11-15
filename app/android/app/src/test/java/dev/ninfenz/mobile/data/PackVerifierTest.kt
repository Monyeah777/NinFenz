package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.FakeCoreBridge
import dev.ninfenz.mobile.core.CoreResponse
import java.nio.file.Files
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PackVerifierTest {

    @Test
    fun callsPackVerifyWithInstalledRoot() = runBlocking {
        val dir = Files.createTempDirectory("nf-pack-verify-test").toFile()
        val bridge = FakeCoreBridge().enqueue(CoreResponse.ok(buildJsonObject { put("verdict", "pass") }))
        val pack = PackEntry("demo-pack", "1.0.0", "示例", "d", 1, "a".repeat(64), dir)

        val response = PackVerifier(bridge).verify(pack)
        assertTrue(response.ok)
        assertEquals("pack-verify", bridge.calls[0].first)
        assertEquals(dir.absolutePath, bridge.calls[0].second["root"]?.jsonPrimitive?.content)
    }
}
