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
}
