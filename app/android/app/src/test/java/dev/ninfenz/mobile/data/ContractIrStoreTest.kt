package dev.ninfenz.mobile.data

import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class ContractIrStoreTest {
    @get:Rule
    val tmp = TemporaryFolder()

    @Test
    fun savesAndLoadsSolveResult() {
        val store = ContractIrStore(tmp.root, "p1")
        val result = buildJsonObject {
            put("schema", "nf-contract-result/1")
            put("satisfiable", true)
        }
        store.saveSolve(result)
        assertEquals("true", store.loadSolve()?.get("satisfiable")?.toString())
    }

    @Test
    fun savesAndLoadsContractValues() {
        val store = ContractIrStore(tmp.root, "p1")
        store.saveValues(mapOf("slot_a" to "hello", "slot_b" to "world"))
        assertEquals("hello", store.loadValues()["slot_a"])
        assertEquals("world", store.loadValues()["slot_b"])
        store.saveValues(mapOf("slot_a" to "", "slot_c" to "new"))
        assertEquals("hello", store.loadValues()["slot_a"])
        assertEquals("new", store.loadValues()["slot_c"])
    }
}
