package dev.ninfenz.mobile

import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.MissingCoreBridge
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
        assertEquals(1, response.resultObject()!!.size)
    }

    @Test
    fun parsesErrorEnvelopeWithPathAndExit() {
        val text = "{\"ok\":false,\"exit\":3,\"result\":null,\"error\":{\"code\":\"NF-SEC-001\",\"message\":\"zip slip\",\"fix\":\"拒绝\",\"path\":\"$.path\"}}"
        val response = CoreResponse.fromEnvelope(text)
        assertFalse(response.ok)
        assertEquals(3, response.exit)
        assertNotNull(response.error)
        assertEquals("NF-SEC-001", response.error!!.code)
        assertEquals("$.path", response.error!!.path)
        assertEquals(3, response.error!!.exit)
    }

    @Test
    fun validateFailureKeepsReportInResult() {
        val text = "{\"ok\":false,\"exit\":1,\"result\":{\"verdict\":\"fail\"},\"error\":{\"code\":\"NF-VAL-001\",\"message\":\"L0 fail\",\"fix\":\"修\"}}"
        val response = CoreResponse.fromEnvelope(text)
        assertFalse(response.ok)
        assertEquals(1, response.exit)
        assertNotNull(response.result)
        assertEquals("fail", response.resultObject()!!["verdict"].toString().trim('"'))
    }

    @Test
    fun rejectsOkExitMismatch() {
        val response = CoreResponse.fromEnvelope("{\"ok\":true,\"exit\":3,\"result\":null,\"error\":null}")
        assertFalse(response.ok)
        assertEquals(CoreResponse.PROTOCOL_CODE, response.error!!.code)
        assertEquals(4, response.exit)
    }

    @Test
    fun rejectsNotOkWithExitZero() {
        val response = CoreResponse.fromEnvelope("{\"ok\":false,\"exit\":0,\"result\":null,\"error\":{\"code\":\"X\",\"message\":\"m\",\"fix\":\"f\"}}")
        assertFalse(response.ok)
        assertEquals(CoreResponse.PROTOCOL_CODE, response.error!!.code)
    }

    @Test
    fun rejectsMissingOkField() {
        val response = CoreResponse.fromEnvelope("{\"exit\":0,\"result\":{}}")
        assertEquals(CoreResponse.PROTOCOL_CODE, response.error!!.code)
    }

    @Test
    fun rejectsMalformedJson() {
        val response = CoreResponse.fromEnvelope("not json at all")
        assertEquals(CoreResponse.PROTOCOL_CODE, response.error!!.code)
        assertEquals(4, response.exit)
    }

    @Test
    fun rejectsErrorEnvelopeWithoutErrorObject() {
        val response = CoreResponse.fromEnvelope("{\"ok\":false,\"exit\":1,\"result\":null,\"error\":null}")
        assertEquals(CoreResponse.PROTOCOL_CODE, response.error!!.code)
    }

    @Test
    fun ignoresFfiTopLevelOpField() {
        val response = CoreResponse.fromEnvelope("{\"ok\":true,\"exit\":0,\"result\":{},\"error\":null,\"op\":\"canonical\"}")
        assertTrue(response.ok)
    }

    @Test
    fun missingCoreBridgeAlwaysReportsNfe005() = runBlocking {
        val bridge = MissingCoreBridge("no .so", "build it")
        assertNull(bridge.abiVersion())
        val response = bridge.call("canonical", buildJsonObject { put("value", 1) })
        assertFalse(response.ok)
        assertEquals("NF-E-005", response.error!!.code)
        assertEquals(4, response.exit)
    }
}
