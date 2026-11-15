package dev.ninfenz.studio

import dev.ninfenz.studio.core.CoreResponse
import dev.ninfenz.studio.core.MissingCoreBridge
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CoreResponseTest {

    @Test
    fun parsesOkEnvelope() {
        val response = CoreResponse.fromEnvelope("{\"ok\":true,\"exit\":0,\"result\":{\"a\":1},\"error\":null}")
        assertTrue(response.ok)
        assertEquals(0, response.exit)
        assertNotNull(response.result)
        assertNull(response.error)
    }

    @Test
    fun parsesErrorEnvelope() {
        val response = CoreResponse.fromEnvelope(
            "{\"ok\":false,\"exit\":3,\"result\":null,\"error\":{\"code\":\"NF-SEC-001\",\"message\":\"zip slip\",\"fix\":\"拒绝\",\"path\":\"$.p\"}}"
        )
        assertFalse(response.ok)
        assertEquals(3, response.exit)
        assertEquals("NF-SEC-001", response.error!!.code)
        assertEquals("$.p", response.error!!.path)
    }

    @Test
    fun rejectsEnvelopeWithOkExitMismatch() {
        val response = CoreResponse.fromEnvelope("{\"ok\":true,\"exit\":1,\"result\":null,\"error\":null}")
        assertFalse(response.ok)
        assertEquals(CoreResponse.PROTOCOL_CODE, response.error!!.code)
    }

    @Test
    fun rejectsMalformedJson() {
        val response = CoreResponse.fromEnvelope("<<>>")
        assertEquals(CoreResponse.PROTOCOL_CODE, response.error!!.code)
        assertEquals(4, response.exit)
    }

    @Test
    fun missingBridgeReportsNfe005() = runBlocking {
        val bridge = MissingCoreBridge("dll not found")
        val response = bridge.call("pack-hash", buildJsonObject { })
        assertEquals("NF-E-005", response.error!!.code)
        assertEquals(4, response.exit)
        assertNull(bridge.abiVersion())
    }
}
