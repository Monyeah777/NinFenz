package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ProtocolDraftStoreTest {
    @Test
    fun savesAndLoadsValuesAndEnabled() {
        val dir = Files.createTempDirectory("nf-protocol-draft").toFile()
        val store = ProtocolDraftStore(dir)
        store.save("p/1", mapOf("F-001" to "alpha"), mapOf("R-001" to true, "R-002" to false))
        val draft = store.load("p/1")
        assertEquals("alpha", draft?.values?.get("F-001"))
        assertEquals(true, draft?.enabled?.get("R-001"))
        assertEquals(false, draft?.enabled?.get("R-002"))
    }

    @Test
    fun clearAndMalformedFileReturnsNull() {
        val dir = Files.createTempDirectory("nf-protocol-draft-2").toFile()
        val store = ProtocolDraftStore(dir)
        store.save("p", mapOf("F-001" to "x"), emptyMap())
        store.clear("p")
        assertNull(store.load("p"))
        val f = java.io.File(dir, "drafts/author-protocol-p.json")
        f.parentFile?.mkdirs()
        f.writeText("{bad", Charsets.UTF_8)
        assertNull(store.load("p"))
    }
}
