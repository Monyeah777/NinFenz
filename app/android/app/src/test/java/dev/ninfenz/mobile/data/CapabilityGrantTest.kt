package dev.ninfenz.mobile.data

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class CapabilityGrantTest {
    @Test
    fun defaultAllowsReadAndExport() {
        val grant = CapabilityGrant.defaultForPackage()
        assertTrue(grant.allows(CapabilityGrant.READ, 0))
        assertTrue(grant.allows(CapabilityGrant.EXPORT, 0))
        assertFalse(grant.allows(CapabilityGrant.COMMENT, 0))
    }

    @Test
    fun expiryAndRevoke() {
        val grant = CapabilityGrant(setOf(CapabilityGrant.READ), expiresAt = 100)
        assertTrue(grant.allows(CapabilityGrant.READ, 99))
        assertFalse(grant.allows(CapabilityGrant.READ, 100))
        assertFalse(CapabilityGrant(setOf(CapabilityGrant.READ), revoked = true).allows(CapabilityGrant.READ, 0))
    }

    @Test
    fun jsonRoundTrip() {
        val grant = CapabilityGrant(setOf(CapabilityGrant.READ, CapabilityGrant.REASSEMBLE), 123)
        val parsed = CapabilityGrant.parse(Json.parseToJsonElement(grant.toJson().toString()).jsonObject)
        assertTrue(parsed.allows(CapabilityGrant.REASSEMBLE, 0))
    }

    @Test
    fun unknownCapRejected() {
        val json = """{"schema":"nf-capability/1","caps":["write"],"revoked":false}"""
        assertThrows(IllegalArgumentException::class.java) {
            CapabilityGrant.parse(Json.parseToJsonElement(json).jsonObject)
        }
    }
}
