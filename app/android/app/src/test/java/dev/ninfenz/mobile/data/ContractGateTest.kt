package dev.ninfenz.mobile.data

import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ContractGateTest {
    @Test
    fun blocksOnlyWhenSolvedUnsatisfiable() {
        assertFalse(ContractGate.blocked(null))
        assertFalse(ContractGate.blocked(buildJsonObject { put("satisfiable", true) }))
        assertTrue(ContractGate.blocked(buildJsonObject { put("satisfiable", false) }))
    }
}
