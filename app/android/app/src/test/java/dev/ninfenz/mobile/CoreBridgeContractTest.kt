package dev.ninfenz.mobile

import dev.ninfenz.mobile.core.CoreResponse
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CoreBridgeContractTest {

    @Test
    fun callCarriesOpAndPayloadVerbatim() = runBlocking {
        val bridge = FakeCoreBridge()
        bridge.enqueue(CoreResponse.ok(buildJsonObject { put("canonical", "x") }))
        val payload = buildJsonObject { put("value", 42) }
        val response = bridge.call("canonical", payload)
        assertTrue(response.ok)
        assertEquals(1, bridge.calls.size)
        assertEquals("canonical", bridge.calls[0].first)
        assertEquals(payload, bridge.calls[0].second)
    }

    @Test
    fun errorExitSemanticsPreserved() = runBlocking {
        val bridge = FakeCoreBridge()
        bridge.enqueue(CoreResponse.failure("NF-PCK-006", "冲突未裁决", "在冲突 UI 逐个决定", 1))
        val response = bridge.call("pack-merge", buildJsonObject { })
        assertEquals("NF-PCK-006", response.error!!.code)
        assertEquals(1, response.exit)
        assertEquals("在冲突 UI 逐个决定", response.error!!.fix)
    }

    @Test
    fun abiVersionReflectsBackend() {
        val bridge = FakeCoreBridge()
        assertEquals("fake-abi/1", bridge.abiVersion())
        bridge.setAbi(null)
        assertNull(bridge.abiVersion())
    }

    @Test
    fun fakeBridgeWithoutQueueFailsClosed() = runBlocking {
        val bridge = FakeCoreBridge()
        val response = bridge.call("graph-validate", buildJsonObject { })
        assertEquals("NF-E-005", response.error!!.code)
        assertEquals(4, response.exit)
    }

    @Test
    fun fakeBridgeRecordsMultipleCallsInOrder() = runBlocking {
        val bridge = FakeCoreBridge()
        bridge.enqueue(CoreResponse.ok(buildJsonObject { }))
        bridge.enqueue(CoreResponse.ok(buildJsonObject { }))
        bridge.call("a", buildJsonObject { })
        bridge.call("b", buildJsonObject { })
        assertEquals(listOf("a", "b"), bridge.calls.map { it.first })
    }
}
